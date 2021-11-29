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
from datetime import datetime

from bottle import Bottle, run, request, template
import requests

# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    #board stores all message on the system 
    board = {} 
    is_leader = False; 
    leader_id = -1;

    def get_time():
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        return current_time


    # Election methods: 
    def start_election():
        global my_id, is_leader, leader_id
        # Send message to all greater ids
        won_election = send_election()
        if won_election:  # maybe put send_election in thread in the future
            try:
                #Propegate election result to all other nodes
                args = ['/election/WINNER/{}'.format(str(my_id))]
                print(args)
                thread = Thread(target=propagate_to_vessels,
                                args=args)
                thread.daemon = True
                thread.start()
                print("I AM KING!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! at " + get_time())
                is_leader = True
                leader_id = my_id
            except Exception as e:
                print e

    def send_election():
        print ("sending election at " + get_time())
        global vessel_list, my_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) > my_id: # only send to greater ids
                print("sending new election too " + vessel_id + " at " + get_time())
                
                success = contact_vessel(vessel_ip, '/election/NEW')
                if success:
                    print("election failed at " + get_time())
                    return False
                if not success:
                    print ("\n\nCould not contact vessel {}\n\n".format(vessel_id))
        print ("election complete at " + get_time())
        return True

    #leader methods: 
    def investigate_add(entry_sequence, element):
        print("investigate_add at " + get_time())
        #investigate if request is valid. 

        #if valid propegate to all nodes and call add_new_element_to_store on self
        try:
            #Propegate request to all other nodes
            new_entry = request.forms.get('entry')
            if len(board) == 0:
                    element_id = 0
            else:
                    element_id = max(board.keys()) + 1 # you need to generate a entry number
            add_new_element_to_store(element_id, new_entry)
            
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/ADD/{}'.format(str(element_id)), {'entry': new_entry}, 'POST'))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False
        

    def investigate_modify(entry_sequence, modified_element):
        print("investigate_modify")
        #investigate if request is valid. 

        #if valid propegate to all nodes and call modify_element_in_store on self

        try:
            #Propegate request to all other nodes
            entry = request.forms.get('entry')
            modify_element_in_store(entry_sequence, modified_element)
            
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/Delete/{}'.format(str(entry_sequence)), {'entry': entry}, 'POST'))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False

    def investigate_delete(entry_sequence):
        print("investigate_delete")
        #investigate if request is valid. 
        
        #if valid propegate to all nodes and call delete_element_from_store on self
        
        try:
            #Propegate request to all other nodes
            entry = request.forms.get('entry')
            delete_element_from_store(entry_sequence)
            
            thread = Thread(target=propagate_to_vessels,
                            args=('/propagate/ADD/{}'.format(str(entry_sequence)), {'entry': entry}, 'POST'))
            thread.daemon = True
            thread.start()
            return True
        except Exception as e:
            print e
        return False


    # Local modification methods:
    def add_new_element_to_store(entry_sequence, element):
        print("add_new_element_to_store")
        global board, my_id, is_leader
        element_id = int(entry_sequence)
        try:
           if entry_sequence not in board:
                board[element_id] = element
                success = True
        except Exception as e:
            print e
        return success
            
        
    def modify_element_in_store(entry_sequence, modified_element):
        print("modify_element_in_store")
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
        print("delete_element_from_store")
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
        print("index")
        global board, my_id
        return template('server/index.tpl', board_title='Vessel {}'.format(my_id),
                board_dict=sorted({"0":board,}.iteritems()), members_name_string='Erik Magnusson, Max Arfvidsson Nilsson')

    @app.get('/board')
    def get_board():
        global board, my_id
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(my_id), board_dict=sorted(board.iteritems()))
    
    #------------------------------------------------------------------------------------------------------
    
    # You NEED to change the follow functions
    @app.post('/board')
    def client_add_received():
        print("client_add_received")
        '''Adds a new element to the board
        Called directly when a user is doing a POST request on /board'''
        global board, my_id, is_leader, leader_id

        if (is_leader):
            investigate_add(entry_sequence, modified_element)
        else:
            try:
                #send request to leader
                new_entry = request.forms.get('entry')
                thread = Thread(target=send_request_to_leader,
                                args=('/request/ADD/', {'entry': new_entry}, 'POST'))
                thread.daemon = True
                thread.start()
                return True
            except Exception as e:
                print e
            return False

    @app.post('/board/<element_id:int>')
    def client_action_received(element_id):
        print("client_action_received")
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
                thread = Thread(target=send_request_to_leader,
                                args=('/request/DELETE/' + str(element_id), {'entry': entry}, 'POST'))
                thread.daemon = True
                thread.start()
        else:
            if is_leader:
                investigate_modify(element_id, entry)
            else: 
                thread = Thread(target=send_request_to_leader,
                                args=('/request/MODIFY/' + str(element_id), {'entry': entry}, 'POST'))
                thread.daemon = True
                thread.start()
        
        print "the delete option is ", delete_option
        
    #With this function you handle requests from other nodes like add modify or delete
    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        print("propagation_received")
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

#This function handles requests to the leader
    @app.post('/request/<action>')
    def request_received(action, element_id):
        print("request_received")
        global is_leader, leader_id
        if not is_leader:
            print("I'm not leader")
        #get entry from http body
        entry = request.forms.get('entry')
        print "the action is", action
        
        if action == "ADD":
            investigate_add(element_id, entry)
        
        elif action == "MODIFY":
            investigate_modify(element_id, entry)
            
        elif action == "DELETE":
            investigate_delete(element_id)
            
        else:
            print("Action not valid")


    @app.post('/election/NEW')
    def new_election_received():
        print("new election recieved at " + get_time())
        # String referrer = request.getHeader("referer")
        # entry = request.forms.get('entry')
        # print(entry)
        # request.forms.get
        # print(referrer)
        print(request.headers.get("referrer"))
        print(request.headers.get("Referrer"))
        start_election()
        return True

    @app.get('/test')
    def test():
        print("Test")
        return "Test"

    @app.post('/election/WINNER/<new_leader_id>')
    def new_leader(new_leader_id):
        global leader_id, is_leader
        print("new leader received " + str(new_leader_id))
        leader_id = new_leader_id
        if is_leader:
            print("I surrender my throne!")
            is_leader = False

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        print("contact_vessel")
        # Try to contact another server (vessel) through a POST or GET, once
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print ('Non implemented feature!')
            # result is in res.text or res.json()
            print(res.text)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        print("propagate_to_vessels")
        global vessel_list, my_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != my_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)
    
    def send_request_to_leader(path, payload = None, req = 'POST'):
        print("send_request_to_leader")
        global my_id, leader_id

        if leader_id < 0:
            print("This is the beginning of the system.")
            print("Starting election process...")
            start_election()

        if int(leader_id) != my_id: # don't propagate to yourself
            success = contact_vessel('10.1.0.{}'.format(str(leader_id)), path, payload, req)
            if not success:
                print "\n\nCould not contact leader {}\n\n".format(leader_id)
                print("starting election....")
                start_election()

        
    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    def main():
        global vessel_list, my_id, app
        print("start of main")
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