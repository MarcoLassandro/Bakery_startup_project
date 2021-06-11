'''
    This file is part of PM4Py (More Info: https://pm4py.fit.fraunhofer.de).

    PM4Py is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PM4Py is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PM4Py.  If not, see <https://www.gnu.org/licenses/>.
'''
import datetime
from copy import copy
from enum import Enum
from random import choice
import random 
import time

from pm4py.objects.log import obj as log_instance
from pm4py.objects.petri_net import semantics
from pm4py.objects.petri_net.obj import PetriNet
from pm4py.util import constants
from pm4py.util import exec_utils
from pm4py.util import xes_constants


class Parameters(Enum):
    """
    
    This is a dictionary where each key is an activity of the given petri net
    and the value indicates the time normally needed to make that activity.
    
    """
    TIME_CONSTRAINTS = "time_constraints"

    """
    
    This is a new parameter that is the timestamp related to the end of an 
    activity.
    
    """
    END_TIMESTAMP_KEY = "end_timestamp" 
    """
    
    This is a dictionary where the key is an activity of the process model and the value is a list 
    containing the first activities that are antecedents to the first 
    
    """
    ANTECEDENTS = "antecedents"
    """
    
    Such parameter is a fraction of the time needed to finish an activity.
    This is used to generate random durations of activities in synthetic logs. 
    
    """ 
    RANDOMNESS_OF_TIMESTAMP = "randomness_of_timestamps"
    ACTIVITY_KEY = constants.PARAMETER_CONSTANT_ACTIVITY_KEY
    TIMESTAMP_KEY = constants.PARAMETER_CONSTANT_TIMESTAMP_KEY
    
    CASE_ID_KEY = constants.PARAMETER_CONSTANT_CASEID_KEY
    RETURN_VISITED_ELEMENTS = "return_visited_elements"
    NO_TRACES = "noTraces"
    MAX_TRACE_LENGTH = "maxTraceLength"



def apply_playout(net, initial_marking, no_traces=100, max_trace_length=100,
                  case_id_key=xes_constants.DEFAULT_TRACEID_KEY,
                  activity_key=xes_constants.DEFAULT_NAME_KEY, timestamp_key=xes_constants.DEFAULT_TIMESTAMP_KEY, end_timestamp_key=xes_constants.DEFAULT_TIMESTAMP_KEY,
                  final_marking=None, return_visited_elements=False, time_constraints = None, antecedents = None, randomness_of_timestamps = 0):
    """
    Do the playout of a Petrinet generating a log

    Parameters
    ----------
    net
        Petri net to play-out
    initial_marking
        Initial marking of the Petri net
    no_traces
        Number of traces to generate
    max_trace_length
        Maximum number of events per trace (do break)
    case_id_key
        Trace attribute that is the case ID
    activity_key
        Event attribute that corresponds to the activity
    timestamp_key
        Event attribute that corresponds to the timestamp
    final_marking
        If provided, the final marking of the Petri net
    """
    # assigns to each event an increased timestamp from 1970
    curr_timestamp = 0
    all_visited_elements = []
    for i in range(no_traces):
        visited_elements = []
        visible_transitions_visited = []
        dict_trans_history = {}   
        
        marking = copy(initial_marking)
        prev_visible_trans = None
        while len(visible_transitions_visited) < max_trace_length:
            visited_elements.append(marking)
                
            if not semantics.enabled_transitions(net, marking):  # supports nets with possible deadlocks
                break
            all_enabled_trans = semantics.enabled_transitions(net, marking)
            if final_marking is not None and marking == final_marking:
                trans = choice(list(all_enabled_trans.union({None})))

            else:
                trans = choice(list(all_enabled_trans))
            if trans is None:
                break
 
            visited_elements.append(trans)
            if trans.label is not None:
                visible_transitions_visited.append(trans)
            marking = semantics.execute(trans, net, marking)

        all_visited_elements.append(tuple(visited_elements))

    if return_visited_elements:
        return all_visited_elements
    
    [print(x+str(dict_trans_history[x])) for x in dict_trans_history]
    
    log = log_instance.EventLog()
    for index, visited_elements in enumerate(all_visited_elements):
        trace = log_instance.Trace()
        trace.attributes[case_id_key] = str(index)
        for i, element in enumerate(visited_elements):
            if type(element) is PetriNet.Transition and element.label is not None:
                event = log_instance.Event()
                event[activity_key] = element.label
                
                #This code is used to generate random timestamps given the time constraints of the current activity event.
                #To work properly the antecedents dictionary should contains for each activity (key) of the process model the first antecedents (a list of activities);
                #More over the time_constraints dictionary should contain for each activity(key) the time expressed in days (for now).
                if antecedents.get(element.label) is not None and time_constraints is not None:
                    #First are retrieved the antecedents of the given activity
                    prev_activity_list = antecedents[element.label]
                    
                    #This retrieves the last event for each antecedent of the given activity 
                    prev_activity = {}
                    for item in trace:
                      if item[activity_key] in prev_activity_list:
                        prev_activity[item[activity_key]] = item
                    
                    #If there are events related to such antecedents the latest one (based on the timestamp of the events)
                    #will be retrieved and its end_timestamp is used as start item of the given activity.
                    if len(prev_activity.items()) == 0:
                        prev_timestamp = datetime.datetime.fromtimestamp(curr_timestamp)  
                    else:
                        temp_v = None
                        for k, v in prev_activity.items():
                            if temp_v is None or v[end_timestamp_key] > temp_v[end_timestamp_key]:
                                temp_v = v
                        prev_activity = temp_v
                        prev_timestamp = prev_activity[end_timestamp_key]
                        
                    ts = time_constraints[event[activity_key]]*60*60*24
                    prev_timestamp_sec = (prev_timestamp-datetime.datetime.fromtimestamp(0)).total_seconds()
                    
                    if randomness_of_timestamps > 0:
                        #Here is generated a random timestamp for the end of an activity, the randomness is given by considering 
                        #The ideal duration of the activity and a fraction of such duration.
                        ts = random.randrange((ts-ts*randomness_of_timestamps), (ts+ts*randomness_of_timestamps))

                    end_timestamp = prev_timestamp_sec + ts
                    
                    event[timestamp_key] = prev_timestamp
                    event[end_timestamp_key] = datetime.datetime.fromtimestamp(end_timestamp)
                else:
                    event[timestamp_key] = datetime.datetime.fromtimestamp(curr_timestamp)
                
                trace.append(event)
                # increases by 1 second
                curr_timestamp += 1
        log.append(trace)


    return log


def apply(net, initial_marking, final_marking=None, parameters=None):
    """
    Do the playout of a Petrinet generating a log

    Parameters
    -----------
    net
        Petri net to play-out
    initial_marking
        Initial marking of the Petri net
    final_marking
        If provided, the final marking of the Petri net
    parameters
        Parameters of the algorithm:
            Parameters.NO_TRACES -> Number of traces of the log to generate
            Parameters.MAX_TRACE_LENGTH -> Maximum trace length
    """

    if parameters is None:
        parameters = {}
    case_id_key = exec_utils.get_param_value(Parameters.CASE_ID_KEY, parameters, xes_constants.DEFAULT_TRACEID_KEY)
    activity_key = exec_utils.get_param_value(Parameters.ACTIVITY_KEY, parameters, xes_constants.DEFAULT_NAME_KEY)
    timestamp_key = exec_utils.get_param_value(Parameters.TIMESTAMP_KEY, parameters,
                                               xes_constants.DEFAULT_TIMESTAMP_KEY)
    no_traces = exec_utils.get_param_value(Parameters.NO_TRACES, parameters, 1000)
    max_trace_length = exec_utils.get_param_value(Parameters.MAX_TRACE_LENGTH, parameters, 1000)
    return_visited_elements = exec_utils.get_param_value(Parameters.RETURN_VISITED_ELEMENTS, parameters, False)
    time_constraints = exec_utils.get_param_value(Parameters.TIME_CONSTRAINTS, parameters, None)
    antecedents = exec_utils.get_param_value(Parameters.ANTECEDENTS, parameters, None)
    end_timestamp_key = exec_utils.get_param_value(Parameters.END_TIMESTAMP_KEY, parameters, Parameters.END_TIMESTAMP_KEY)
    randomness_of_timestamps = exec_utils.get_param_value(Parameters.RANDOMNESS_OF_TIMESTAMP, parameters, 0)

    return apply_playout(net, initial_marking, max_trace_length=max_trace_length, no_traces=no_traces,
                         case_id_key=case_id_key, activity_key=activity_key, timestamp_key=timestamp_key, end_timestamp_key = end_timestamp_key,
                         final_marking=final_marking, return_visited_elements=return_visited_elements, time_constraints=time_constraints, antecedents = antecedents, randomness_of_timestamps = randomness_of_timestamps)
