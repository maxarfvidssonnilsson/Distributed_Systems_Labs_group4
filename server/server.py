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
from threading import Thread

from bottle import Bottle, run, request, template
import requests
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    #board stores all message on the system 
    board = {0 : "Welcome to Distributed Systems Course"} 


    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    
    #This functions will add an new element
    def add_new_element_to_store(element_id: int, element, element_specific_vector_clock, element_specific_time_stamp):
        global board, my_id
        success = False
        try:
           if element_id not in board:
               if
                board[element_id] = (element, element_specific_vector_clock, element_specific_time_stamp)
                success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element):
        global board, my_id
        success = False
        element_id = int(entry_sequence)
        try:
            if element_id in board:
                board[element_id] = modified_element
                success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence):
        global board, my_id
        success = False
        element_id = int(entry_sequence)
        popped = board.pop(element_id, False)
        if popped:
            success = True
        else:
            print("Value to delete not found")
        return success

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
        global board, my_id, vector_clock
        try:
            new_entry = request.forms.get('entry')
            #element_id = max(board.keys()) + 1 # you need to generate a entry number
            element_id = hash(new_entry + str(time.time()))
            vector_clock[str(my_id)] += 1
            add_new_element_to_store(element_id, new_entry, vector_clock)

            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/ADD/' + str(element_id), {'entry': new_entry, 'vector_clock': vector_clock}, 'POST'))
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
        entry = request.forms.get('entry')
        
        delete_option = request.forms.get('delete')
        #0 = modify, 1 = delete
        if delete_option == '1':
            delete_element_from_store(element_id, False)
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/DELETE/' + str(element_id), {'entry': entry}, 'POST'))
            thread.daemon = True
            thread.start()
        else:
            modify_element_in_store(element_id, entry, False)
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/MODIFY/' + str(element_id), {'entry': entry}, 'POST'))
            thread.daemon = True
            thread.start()
        
        print "the delete option is ", delete_option
        
        

    #With this function you handle requests from other nodes like add modify or delete
    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        #get entry from http body
        entry = request.forms.get('entry')
        print "the action is", action
        
        if action == "ADD":
            add_new_element_to_store(element_id, entry, True)
        
        elif action == "MODIFY":
            modify_element_in_store(element_id, entry, True)
            
        elif action == "DELETE":
            delete_element_from_store(element_id, True)
            
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