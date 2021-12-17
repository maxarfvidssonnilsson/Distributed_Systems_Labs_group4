# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: Erik Magnusson, Max Arfvidsson Nilsson
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse
import copy
from threading import Thread

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------

# Post class is added to keep track of all the data related to each post and to streamline caprisons between different posts. 
class Post:
    def __init__(self, action, post_id, message, vector_clock, time_stamp):
        self.action = action
        self.post_id = post_id
        self.message = message
        self.vector_clock = vector_clock
        self.time_stamp = time_stamp

    # Comparison method that is automatically called when a comparison between two posts is made. e.g. post1 > post2
    # This comparison is used to consistelty determine the order of messages, and modification to messages. 
    def __lt__(self, other):
        # First we compare based on vector clocks. 
        if compare_vector_clocks(self.vector_clock, other.vector_clock): 
            return False
        elif compare_vector_clocks(other.vector_clock, self.vector_clock):
            return True
        else: 
            # If the vector clocks are in conflict we instead compare based on timestamps.
            if self.time_stamp > other.time_stamp:
                return False
            elif other.time_stamp > self.time_stamp:
                return True
            else:
                # If the timestamps are equal we resolve what message to pick based on alphabetical order. 
                # This makes sure we always have to same outcome in every node. 
                if self.message < other.message:
                    return False
                else:
                    return True
    
# Returns True if clock_one is bigger or equals to clock_two for all nodes. 
def compare_vector_clocks(clock_one, clock_two):
    for key in clock_one:
        if clock_one[key] < clock_two[key]:
            return False
    return True

try:
    app = Bottle()

    #board stores all message on the system 
    board = {}

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    
    # This function will add a new post
    def add_new_post_to_store(post):
        global board, my_id
        success = False
        try:
           if post.post_id not in board:
                # We do a deep copy so that edits in board wont change board_history. 
                board[post.post_id] = copy.deepcopy(post)
                success = True
        except Exception as e:
            print e
        return success

    # This function will modify a post
    def modify_post_in_store(post):
        global board, my_id
        success = False
        try:
            if post.post_id in board:
                # Only the message is changed so that we still have the original timestamp and v-clock. 
                board[post.post_id].message = post.message
                success = True
        except Exception as e:
            print e
        return success

    # This function will modify a post 
    def delete_post_from_store(post):
        global board, my_id
        success = False
        popped = board.pop(post.post_id, False)
        if popped:
            success = True
        else:
            print("Value to delete not found")
        return success

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, my_id
        if len(board) == 0:
            board_iter = []
        else:
            board_iter = [(v.post_id, v.message) for v in sorted(board.values())]
        return template('server/index.tpl', board_title='Vessel {}'.format(my_id),
                board_dict=board_iter, members_name_string='Erik Magnusson, Max Arfvidsson Nilsson')

    @app.get('/board')
    def get_board():
        global board, my_id
        if len(board) == 0:
            board_iter = []
        else:
            board_iter = [(v.post_id, v.message) for v in sorted(board.values())]
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(my_id), board_dict=board_iter)
     
    @app.post('/board')
    def client_add_received():
        '''Adds a new post to the board
        Called directly when a user is doing a POST request on /board'''
        global board, my_id, vector_clock, board_history
        try:
            message = request.forms.get('entry')
            time_stamp = time.time()
            
            # Timestamp is added to the hash so that messages with the same text don't get the same hash.
            # my_id is also added so that in the rare case that two nodes post the same message at the same 
            # time they don't become the same message. 
            post_id = hash(message + str(time_stamp) + str(my_id))  

            vector_clock[str(my_id)] += 1
            new_post = Post('ADD', post_id, message, copy.deepcopy(vector_clock), time_stamp)

            # When adding things localy we can be sure that it won't conflict with posts already on the board. 
            add_new_post_to_store(new_post)
            board_history.append(new_post)

            threaded_propagate_to_vessels('/propagate/ADD/' + str(post_id), {'entry': new_post.message, 
                'vector_clock': json.dumps(new_post.vector_clock), 'time_stamp': new_post.time_stamp})
            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<post_id:int>/')
    def client_action_received(post_id):
        global board, my_id
        
        print("You receive a post")
        print("id is ", my_id)
        
        # Get the entry from the HTTP body
        message = request.forms.get('entry')
        delete_option = 'DELETE' if request.forms.get('delete') == '1' else 'MODIFY'
        time_stamp = time.time()
        vector_clock[str(my_id)] += 1
        new_post = Post(delete_option, post_id, message, copy.deepcopy(vector_clock), time_stamp)

        board_history.append(new_post)
        # When deleting or modifying things localy we can be sure that the action won't have a conflict
        # with what is already in the board. 
        if delete_option == 'DELETE': 
            delete_post_from_store(new_post)
        else:
            modify_post_in_store(new_post)
        
        threaded_propagate_to_vessels('/propagate/' + delete_option + '/' + str(post_id), {'entry': new_post.message, 
                'vector_clock': json.dumps(new_post.vector_clock), 'time_stamp': new_post.time_stamp})
        
    # Update foriegn parts of own vector clock to match incoming vector clock 
    def update_vector_clock(new_vector_clock):
        global vector_clock, my_id
        for key in vector_clock:
            if key != str(my_id):
                vector_clock[key] = max(vector_clock[key], new_vector_clock[key])
        

    #With this function you handle requests from other nodes like add modify or delete
    @app.post('/propagate/<action>/<post_id>')
    def propagation_received(action, post_id):
        #get entry from http body
        message = request.forms.get('entry')
        print("Incoming vector clock" + (request.forms.get('vector_clock')))
        input_vector_clock = json.loads(request.forms.get('vector_clock'))
        time_stamp = float(request.forms.get('time_stamp'))
        print "the action is", action
        update_vector_clock(input_vector_clock)
        new_post = Post(action, int(post_id), message, input_vector_clock, time_stamp)
        resolve_action(new_post)
    
   
   # This method checks to see that a new post doesn't conflict with the current board history. 
   # If there is a conflict with the last post in board history reslove board is called.
    def resolve_action(new_post):
        global board_history
        # if the board is empty there is no conflict. 
        # new_post > board_history can be done becuase of the built in comparison method in the Post class. 
        if len(board_history) == 0 or new_post > board_history[-1]: 
            board_history.append(new_post)
            apply_action(new_post)
        else:
            resolve_board(new_post)

    # This method slots in a new post in the right place in board_history
    def resolve_board(new_post):
        global board, board_history
        sorted_history = []
        board_resolved = False
        # boar_history is looped through until a place where new_post first is found
        # new_post is placed in the correct slot and board_history is updated. 
        for historic_entry in board_history:
            # new_post > historic_entry can be done becuase of the built in comparison method in the Post class. 
            if board_resolved == True or new_post > historic_entry: 
                sorted_history.append(historic_entry)
            else:
                sorted_history.append(new_post)
                sorted_history.append(historic_entry)
                board_resolved = True
        board_history = sorted_history

        # board is updated by re-applying the entire board_history on an empty board
        board = []
        for historic_entry in board_history:
            apply_action(historic_entry)

    # This method simply applies an action based on a post. 
    def apply_action(post):
        action = post.action
        if action == "ADD":
            add_new_post_to_store(post)
        elif action =="MODIFY":
            modify_post_in_store(post)
        elif action == "DELETE":
            delete_post_from_store(post)
        else:
           print("Action not valid")

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, my_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != my_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)
    
    def threaded_propagate_to_vessels(path, payload = None, req = 'POST'):
        thread = Thread(target=propagate_to_vessels,
                            args=(path, payload, req))
        thread.daemon = True
        thread.start()

        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, my_id, app, vector_clock, board_history, entry_sequence

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        my_id = args.nid
        vessel_list = dict()
        vector_clock = dict()
        board_history = []
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
            vector_clock[str(i)] = 0

        try:
            run(app, host=vessel_list[str(my_id)], port=port)
        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
        
        
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)