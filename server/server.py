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

    # ------------------------------------------------------------------------------------------------------
    # LEADER FUNCTIONS
    # The following three methods are only called in the leader when a node (including the leader) tries to perform any of the tree basic acctions. 
    # ------------------------------------------------------------------------------------------------------
    
    # This function is called in the leader when another node or the leader itself tries to add a new entry to the board. 
    # Currently we consider all requests valid, but we might add conditions in the future. 
    def investigate_add(entry):
        global board
        try:
            # Leader is responsible for assigning an ID to each post.
            # Since the leader is the only one who can set ID's they should be consistant over all nodes. 
            # We assume new posts come into the leader in the order that they were created.
            if len(board) == 0:
                    element_id = 0
            else:
                    element_id = max(board.keys()) + 1 
            add_new_element_to_store(element_id, entry) # makes sure it is added locally

            #Propegate the new item to all other nodes
            threaded_propagate_to_vessels('/propagate/ADD/{}'.format(str(element_id)), {'entry': entry})

            return True
        except Exception as e:
            print e
        return False
        

    def investigate_modify(element_id, new_state):
        global board

        #investigate if request is valid. 
        if int(element_id) not in board:
            print("this element doesn't exist")
            return False
        
        #if valid propegate to all nodes and call modify_element_in_store on self
        try:
            modify_element_in_store(element_id, new_state) # makes sure it is added locally
            threaded_propagate_to_vessels('/propagate/MODIFY/{}'.format(str(element_id)), {'entry': new_state})
            return True
        except Exception as e:
            print e
        return False

    def investigate_delete(element_id):
        global board
        
        #investigate if request is valid. 
        if int(element_id) not in board:
            print("this element doesn't exist")
            return False

        #if valid propegate to all nodes and call delete_element_from_store on self
        try:
            delete_element_from_store(element_id) # makes sure it is added locally
            threaded_propagate_to_vessels('/propagate/DELETE/{}'.format(str(element_id)))
            return True
        except Exception as e:
            print e
        return False

    # Used whenever a non leader process wants to do something and needs to communicate with the leader.
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

    def start_election():
        global my_id, vessel_list, is_leader
        # Bully election algorithm that sends messages to larger IDs one at a time and withdraws if any respond
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
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    
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
    # OLD ROUTE FUNCTIONS (some are modified)
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, my_id
        return template('server/index.tpl', board_title='Vessel {}'.format(my_id),
                board_dict=sorted({"0":board,}.iteritems()), members_name_string='Erik Magnusson, Max Arfvidsson Nilsson')

    @app.get('/board')
    def get_board():
        global board, my_id
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(my_id), board_dict=sorted(board.iteritems()))
    
    @app.post('/board')
    def client_add_received():
        global board, my_id, leader_ip, is_leader
        try:
            new_entry = request.forms.get('entry')
            # Instead of simply posting the node instead sends a request to the leader. 
            if is_leader:   
                # If you are leader you can call investigate directly on yourself
                investigate_add(new_entry) 
            else:
                # Otherwise you send a request to the leader. 
                send_request_to_leader('/request/ADD', {'entry': new_entry})
            return True
        except Exception as e:
            print e
        return False

    #this method hasn't changed, but is now only called by the leader. 
    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, my_id
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
               
        
    @app.post('/propagate/<action>/<element_id>')
    def propagation_received(action, element_id):
        #get entry from http body
        entry = request.forms.get('entry')
        
        if action == "ADD":
            add_new_element_to_store(element_id, entry, True)
        
        elif action == "MODIFY":
            modify_element_in_store(element_id, entry, True)
            
        elif action == "DELETE":
            delete_element_from_store(element_id, True)
            
        else:
            print("Action not valid")

    # ------------------------------------------------------------------------------------------------------
    # NEW ROUTE FUNCTIONS
    # ------------------------------------------------------------------------------------------------------

    #This is called when a new election is started by another node.
    @app.post('/election/NEW')
    def new_election_received():
        from_id = request.forms.get('id')
        print("new election recieved from " + from_id)
        start_election()
        return "Bully"

    # This is called when another node believes it has won the election. 
    @app.post('/election/WINNER/<new_leader_id>')
    def new_leader_received(new_leader_id):
        global leader_id, leader_ip, is_leader, my_id
        if (new_leader_id > my_id):
            print("Recieved new leader " + new_leader_id)
            leader_id = int(new_leader_id)
            leader_ip = '10.1.0.{}'.format(str(leader_id))
            is_leader = False
        else:
            # If the new leader has a lower ID than the current node it starts a new election.
            # This is only a precaution should only be called if some message wasn't recieved. 
            start_election()

    # Handles requests to add a post, sent from a lower node to leader
    @app.post('/request/ADD')
    def new_add_request_received():
        global is_leader
        if not is_leader:
            # If a non leader node recieves a leader call a new election is needed to synchronize the nodes. 
            print("I'm not leader")
            start_election() 
            return
        print("Adding entry")
        entry = request.forms.get('entry')
        investigate_add(entry)

    #This function handles requests to the leader
    @app.post('/request/<action>/<element_id>')
    def request_received(action, element_id):
        global is_leader
        if not is_leader:
            # If a non leader node recieves a leader call a new election is needed to synchronize the nodes. 
            print("I'm not leader")
            start_election()
            return
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

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, my_id

        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != my_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # Simply calls contact_vessel in a thread. 
    def threaded_contact_vessel(vessel_ip, path, payload=None, req='POST'):
        thread = Thread(target=contact_vessel, args=(vessel_ip, path, payload, req))
        thread.daemon = True
        thread.start()
    # Same here but for propogate_to_vessels
    def threaded_propagate_to_vessels(path, payload = None, req = 'POST'):
        thread = Thread(target=propagate_to_vessels, args=(path, payload, req))
        thread.daemon = True
        thread.start()


        
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
    if __name__ == '__main__':
        main()
        
        
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)