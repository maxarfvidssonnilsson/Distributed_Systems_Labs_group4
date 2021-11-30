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
    is_leader = False
    leader_id = -1
    #board stores all message on the system 
    board = {0 : "Welcome to Distributed Systems Course"} 



 #leader methods: 
    def investigate_add(entry):
        global board
        #if valid propegate to all nodes and call add_new_element_to_store on self
        #TODO add checks if it is valid request
        try:
            #Propegate request to all other nodes
            if len(board) == 0:
                    element_id = 0
            else:
                    element_id = max(board.keys()) + 1 # you need to generate a entry number
            add_new_element_to_store(element_id, entry)
            threaded_propagate_to_vessels('/propagate/ADD/{}'.format(str(element_id)), {'entry': entry})
            return True
        except Exception as e:
            print e
        return False
        

    def investigate_modify(element_id, new_state):
        global board

        #investigate if request is valid. 
        if not element_id in board:
            print("this element doesn't exist")
            return False
        
        #if valid propegate to all nodes and call modify_element_in_store on self
        try:
            #Propegate request to all other nodes
            modify_element_in_store(element_id, new_state)
            threaded_propagate_to_vessels('/propagate/MODIFY/{}'.format(str(element_id)), {'entry': new_state})
            return True
        except Exception as e:
            print e
        return False

    def investigate_delete(element_id):
        global board
        
        #investigate if request is valid. 
        if not element_id in board:
            print("this element doesn't exist")
            return False

        #if valid propegate to all nodes and call delete_element_from_store on self
        try:
            #Propegate request to all other nodes
            delete_element_from_store(element_id)
            threaded_propagate_to_vessels('/propagate/DELETE/{}'.format(str(element_id)))
            return True
        except Exception as e:
            print e
        return False

    def send_request_to_leader(path, payload = None, req = 'POST'):
        global my_id, leader_id, my_id

        if leader_id < 0:
            print("This is the beginning of the system.")
            print("Starting election process...")
            start_election()
        elif int(leader_id) != my_id: # don't propagate to yourself
            success = contact_vessel('10.1.0.{}'.format(str(leader_id)), path, payload, req)
            if not success:
                print "\n\nCould not contact leader {}\n\n".format(leader_id)
                print("starting election....")
                start_election()

    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # You will probably need to modify them
    # ------------------------------------------------------------------------------------------------------
    
    #This functions will add an new element
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, my_id
        success = False
        element_id = int(entry_sequence)
        try:
           if entry_sequence not in board:
                board[element_id] = element
                success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
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

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
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
        global board, my_id, leader_ip, is_leader
        try:
            new_entry = request.forms.get('entry')
            if is_leader:   
                investigate_add(new_entry)
            else:
                send_request_to_leader('/request/ADD', {'entry': new_entry})
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
            if is_leader:
                investigate_delete(element_id)
            else:
                send_request_to_leader('/request/DELETE/' + str(element_id), {'entry': entry})
        else:
            if is_leader:
                investigate_modify(element_id, entry)
            else: 
                send_request_to_leader('/request/MODIFY/' + str(element_id), {'entry': entry})
               
        
        
        

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

    
    @app.post('/election/NEW')
    def new_election_received():
        from_id = request.forms.get('id')
        print("new election recieved from " + from_id)
        start_election()
        return "Bully"

    @app.post('/election/WINNER/<new_leader_id>')
    def new_leader_received(new_leader_id):
        global leader_id, leader_ip, is_leader, my_id
        if (new_leader_id > my_id):
            print("Recieved new leader " + new_leader_id)
            leader_id = int(new_leader_id)
            leader_ip = '10.1.0.{}'.format(str(leader_id))
            is_leader = False
        else:
            start_election()

    @app.post('/request/ADD')
    def new_add_request_received():
        print("Adding entry")
        entry = request.forms.get('entry')
        investigate_add(entry)

    #This function handles requests to the leader
    @app.post('/request/<action>/<element_id>')
    def request_received(action, element_id):
        global is_leader
        if not is_leader:
            print("I'm not leader")
        #get entry from http body
        entry = request.forms.get('entry')
        print("the action is", action)
        
        if action == "MODIFY":
            investigate_modify(element_id, entry)
            
        elif action == "DELETE":
            investigate_delete(element_id)
            
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

    def threaded_contact_vessel(vessel_ip, path, payload=None, req='POST'):
        thread = Thread(target=contact_vessel, args=(vessel_ip, path, payload, req))
        thread.daemon = True
        thread.start()

    def threaded_propagate_to_vessels(path, payload = None, req = 'POST'):
        thread = Thread(target=propagate_to_vessels, args=(path, payload, req))
        thread.daemon = True
        thread.start()

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, my_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != my_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    

    # ------------------------------------------------------------------------------------------------------
    # LEADER FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def start_election():
        global my_id, vessel_list, is_leader
        # Send message to largest id, break if any return
        # Could put a flag so process waits for election to finish before starting a new one, ongoing_election
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) > my_id:
                print("Sending election to: " + vessel_id)
                success = contact_vessel(vessel_ip, '/election/NEW',  {'id': my_id})
                if success:
                    print("Lost election to: " + vessel_id)
                    return
                if not success:
                    print ("\n\nCould not contact vessel {}\n\n".format(vessel_id))
        print("I'm the king!!!")
        is_leader = True
        threaded_propagate_to_vessels('/election/WINNER/' + str(my_id))
        return True

        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, my_id, app

        port = 80
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        my_id = args.nid
        vessel_list = dict()
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv+1):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

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