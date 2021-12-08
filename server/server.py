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

class Element:
    def __init__(self, action: str, element_id: int, message: str, vector_clock: dict, time_stamp: int):
        self.action = action
        self.element_id = element_id
        self.message = message
        self.vector_clock = vector_clock
        self.time_stamp = time_stamp
        
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

try:
    app = Bottle()

    #board stores all message on the system 
    board = {0 : "Welcome to Distributed Systems Course"} 


    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    
    #This functions will add an new element
    def add_new_element_to_store(element: Element):
        global board, my_id
        success = False
        try:
           if entry_sequence not in board:
                board[element.element_id] = element.message
                success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(element: Element):
        global board, my_id
        success = False
        element_id = int(element.element_id)
        try:
            if element_id in board:
                board[element_id] = element.message
                success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(element):
        global board, my_id
        success = False
        popped = board.pop(element.element_id, False)
        if popped:
            success = True
        else:
            print("Value to delete not found")
        return success

    #------------------------------------------------
    # HELPER METHODS:
    #------------------------------------------------

    # def sort_board():
    #     global board
    #     sorted_board = {}
    #     for i in range(0, len(board)):
    #         smallest_element = None
    #         biggest_key = None

    #         for key, element in board.items():
    #             old_smallest_element = (smallest_element[3],smallest_element[4],smallest_element[5])
    #             old_element = (element[3],element[4],element[5])

    #             if smallest_element == determine_newest(old_smallest_element,old_element):
    #                 smallest_element = element
    #                 biggest_key = key

    #         if smallest_element == None:
    #             break
    #         sorted_board[biggest_key] = smallest_element
    #     board = sorted_board


 

    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    #No need to modify this
    @app.route('/')
    def index():
        global board, my_id
        return template('server/index.tpl', board_title='Vessel {}'.format(my_id),
                board_dict=sorted({"0":board,}.iteritems()), members_name_string='Erik Magnusson, Max Arfvidsson Nilsson')

    @app.get('/board')
    def get_board():
        global board, my_id
        print board
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(my_id), board_dict=sorted(board.iteritems()))
    
    #------------------------------------------------------------------------------------------------------
    
    # You NEED to change the follow functions
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, my_id, vector_clock, board_history
        try:
            message = request.forms.get('entry')
            time_stamp = time.time()
            element_id = hash(message + str(time_stamp))
            vector_clock[str(my_id)] += 1
            new_element = Element('ADD', element_id, message, copy.deepcopy(vector_clock), time_stamp)
            add_new_element_to_store(new_element)
            board_history.append(new_element)

            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/ADD/' + str(element_id), {'entry': new_element.message, 
                                'vector_clock': new_element.vector_clock, 'time_stamp': new_element.time_stamp}, 'POST'))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False

    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, my_id
        
        print "You receive an element"
        print "id is ", my_id
        # Get the entry from the HTTP body
        message = request.forms.get('entry')
        time_stamp = time.time()
        vector_clock[str(my_id)] += 1
        board_history.append(new_element)
        delete_option = request.forms.get('delete')
        #0 = modify, 1 = delete
        if delete_option == '1':
            
            new_element = Element('DELETE', element_id, message, copy.deepcopy(vector_clock), time_stamp)
            delete_element_from_store(element_id, False)
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/DELETE/' + str(element_id), {'entry': new_element.message, 
                                'vector_clock': new_element.vector_clock, 'time_stamp': new_element.time_stamp}, 'POST'))
            thread.daemon = True
            thread.start()
        else:
            new_element = Element('MODIFY', element_id, message, copy.deepcopy(vector_clock), time_stamp)
            modify_element_in_store(element_id, entry, False)
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/MODIFY/' + str(element_id), {'entry': new_element.message, 
                                'vector_clock': new_element.vector_clock, 'time_stamp': new_element.time_stamp}, 'POST'))
            thread.daemon = True
            thread.start()
        
        print "the delete option is ", delete_option
        
    def update_vector_clock(new_vector_clock):
        global vector_clock, my_id
        for key in vector_clock:
            if key != str(my_id):
                vector_clock[key] = max(vector_clock[key], new_vector_clock[key])
        

    #With this function you handle requests from other nodes like add modify or delete
    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        #get entry from http body
        message = request.forms.get('entry')
        input_vector_clock = request.forms.get('vector_clock')
        time_stamp = request.forms.get('time_stamp')
        print "the action is", action
        update_vector_clock(input_vector_clock)
        new_input = Element(action, int(element_id), message, input_vector_clock, time_stamp)
        resolve_action(new_input)


    def apply_action(element: Element):
        action = element.action
        if action == "ADD":
            add_new_element_to_store(element.element_id, element.message, element.vector_clock, element.time_stamp)
        elif action =="MODIFY":
            modify_element_in_store(element.element_id, element.message)
        elif action == "DELETE":
            delete_element_from_store(element.element_id)
        else:
           print("Action not valid")

    def resolve_action(new_input: Element):
        global board_history
        action = new_input[0]
        if (new_input == determine_newest(new_input, board_history[-1])):
            board_history.append(new_input)
            apply_action(new_input)
        else:
            resolve_board(new_input)

    def resolve_board(new_input: Element):
        global board, board_history
        sorted_history = []
        board_resolved = False
        for historic_entry in board_history:
            if board_resolved == True or new_input == determine_newest(historic_entry, new_input):
                sorted_history.append(historic_entry)
            else:
                sorted_history.append(new_input)
                sorted_history.append(historic_entry)
                board_resolved = True
        board_history = sorted_history

        board = []
        for historic_entry in board_history:
            apply_action(historic_entry)

    def determine_newest(element_1: Element, element_2: Element):
        # First we compare based on vector clocks. 
        if compare_vector_clocks(element_1.vector_clock, element_2.vector_clock): 
            return element_1
        elif compare_vector_clocks(element_2.vector_clock, element_1.vector_clock):
            return element_2
        else: 
            # If the vector clocks are in conflict we instead compare based on timestamps.
            if element_1.time_stamp > element_2.time_stamp:
                return element_1
            elif element_2.time_stamp > element_1.time_stamp:
                return element_2
            else:
                # If the timestamps are equal we resolve what message to pick based on alphabetical order. 
                # This makes sure we always have to same outcome in every node. 
                if element_1.message < element_2.message:
                    return element_1
                else:
                    return element_2
                    
    # Returns True if clock_one is bigger or equals to clock_two for all nodes. 
    def compare_vector_clocks(clock_one, clock_two):
        for key in clock_one:
            if clock_one[key] < clock_two[key]:
                return False
        return True

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

        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, my_id, app, vector_clock

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        my_id = args.nid
        vessel_list = dict()
        vector_clock = dict()
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