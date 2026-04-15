import argparse
import itertools
from typing import Tuple, Any

import numpy
import pandas as pd
from ortools.linear_solver import pywraplp

from src.inputs import args, logger
from src.utils import read_file, write_output
from src.constants import (
    Task, GridValue, DetectionKey, Column, room,
    ROOM_PREFIX, ROOM_LIST_1_TO_14, ROOM_LIST_1_TO_6, ROOM_LIST_1_TO_5,
    HIGH_COST_TASKS, PARTTIME_EXCLUDED,
)


def checkKey(providers: numpy.ndarray, dict, key_list, key):
    #print("14------list providers: {0}".format(providers))
    #print("15------key: {0}".format(key))
    taskScheduled = 0
    keysToCheck = {}
    j = key_list[1]
    k = key_list[2]
    for i in providers:
        keysToCheck[i, j, k] = 1
    #print("21------keys in keysToCheck: {0}".format(keysToCheck.keys()))
    for key in keysToCheck:
        if key in dict.keys():
            taskScheduled = 1
            return taskScheduled
    return taskScheduled


Room_list = ROOM_LIST_1_TO_14

def checkIfAssigned(providers: numpy.ndarray, dict, key_list, key, RoomListToCheck=Room_list):
    #print("34------list providers: {0}".format(providers))
    #print("36------key: {0}".format(key))
    taskScheduled = 0
    keysToCheck = {}
    i = key_list[0]
    j = key_list[1]
    #k = key_list[2]
    for k in RoomListToCheck:
        keysToCheck[i, j, k] = 1
    #print("44------keys in keysToCheck: {0}".format(keysToCheck.keys()))
    for key in keysToCheck:
        if key in dict.keys():
            taskScheduled = 1
            return taskScheduled
    return taskScheduled

def checkIfInRefX(providers: numpy.ndarray, dict, key_list, key, RoomListToCheck=Room_list):
    #print("52------get to checkIfInRefX".format(  ))
    if checkKey(providers, dict, key_list, key) == 0 and checkIfAssigned(providers, dict, key_list, key) == 0:
        return 0
    if max(checkKey(providers, dict, key_list, key), checkIfAssigned(providers, dict, key_list, key)) > 0:
        return 1


def get_sol(x: dict, assigned: dict, days: Any, providers=Any) -> pd.DataFrame:
    """
    Given the solution create a dataframe with the assignment
    :param x: assignment solution
    :param assigned: if an task/or is already assigned
    :param days: list of days
    :param providers: list of providers
    :return: dataframe of assignments for each provider for each day
    """

    keyInX = list(x.keys())[0]
    valueInX = list(x.values())[0]
    print("83------X: {0} {1}".format(keyInX, valueInX))

    keyInAssigned = list(assigned.keys())[0]
    valueInAssigned = list(assigned.values())[0]
    print("87------X: {0} {1}".format(keyInAssigned, valueInAssigned))

    df = pd.DataFrame(index=providers, columns=days)

    for (i, j, k), val in x.items():
        if k not in [Task.BACKUP1, Task.BACKUP2]:
            if val.solution_value() + assigned[i, j, k] == 1:
                df.loc[i, j] = k
    return df



def get_optimal_pain(x: Any, providers, days: numpy.ndarray, ors: numpy.ndarray, cost: dict,
                     specialty1_cost: dict, avail: dict, assigned: dict):
    """
    Given the solution convert to dataframe with average pain and total pain for each provider
    :param x: assignment variable
    :param providers: list of providers
    :param days: list of days
    :param ors: list of ors
    :param cost: cost for each task
    :param specialty1_cost: cost for specialty1 assignment
    :param avail: if SiteA Room assignment needs to be done
    :param assigned: if a room is already assigned
    :return: dataframe with average and total pain for each provider
    """
    df = pd.DataFrame(index=providers,
                      columns=[Column.AVG_COST, Column.TOTAL_COST, Column.ROOM_DAYS, Column.TOTAL_ROOM_COST, Column.AVG_ROOM_COST,
                               Task.ROOM_1, Task.ROOM_2, Task.ROOM_3, Task.ROOM_4, Task.ROOM_5])
    if x is not None:
        for i in providers:
            room_days = sum([min(avail[i, j] + sum([assigned[i, j, k] for k in ors]), 1) for j in days])
            if room_days > 0:
                df.loc[i, Column.TOTAL_COST] = sum([cost[k] * (x[i, j, k].solution_value() +
                                                          assigned[i, j, k]) for j in days for k in ors]) + specialty1_cost[
                                              i]
                df.loc[i, Column.TOTAL_ROOM_COST] = sum([cost[k] * (x[i, j, k].solution_value() +
                                                                assigned[i, j, k]) for j in days for k in ors])
                df.loc[i, Column.ROOM_DAYS] = room_days
                df.loc[i, Column.SLOTS_TO_ASSIGN] = sum([x[i, j, k].solution_value() for j in days for k in ors])
                for k in ROOM_LIST_1_TO_5:
                    df.loc[i, k] = sum([x[i, j, k].solution_value() + assigned[i, j, k] for j in days])
    else:
        for i in providers:
            room_days = sum([min(avail[i, j] + sum([assigned[i, j, k] for k in ors]), 1) for j in days])
            if room_days > 0:
                df.loc[i, Column.TOTAL_COST] = sum([cost[k] * (assigned[i, j, k]) for j in days for k in ors]) + specialty1_cost[
                    i]
                df.loc[i, Column.TOTAL_ROOM_COST] = sum([cost[k] * (assigned[i, j, k]) for j in days for k in ors])
                df.loc[i, Column.ROOM_DAYS] = room_days
                df.loc[i, Column.SLOTS_TO_ASSIGN] = sum([x[i, j, k].solution_value() for j in days for k in ors])
                for k in ROOM_LIST_1_TO_5:
                    df.loc[i, k] = sum([assigned[i, j, k] for j in days])

    df[Column.AVG_COST] = df[Column.TOTAL_COST] / df[Column.ROOM_DAYS]
    df[Column.AVG_ROOM_COST] = df[Column.TOTAL_ROOM_COST] / df[Column.ROOM_DAYS]
    return df


def initialize_decision_variables(providers: numpy.array, days: numpy.array, ors: numpy.array, newPeriod: list, solver: Any,
                                  assigned: dict, avail: dict) -> dict:
    x = {}
    for i, j, k in itertools.product(providers, days, ors):
        if newPeriod[0] > j:
            x[i, j, k] = solver.IntVar(0, 0, f'x[{i}, {j}, {k}]')
        elif assigned[i, j, k] == 1:
            x[i, j, k] = solver.IntVar(0, 0, f'x[{i}, {j}, {k}]')
        elif k in ors[21:]:
            x[i, j, k] = solver.IntVar(0, 0, f'x[{i}, {j}, {k}]')
        elif avail[i, j] == 0:
            x[i, j, k] = solver.IntVar(0, 0, f'x[{i}, {j}, {k}]')
        else:
            x[i, j, k] = solver.IntVar(0, 1, f'x[{i}, {j}, {k}]')
    return x

# all the objective funcitons are listed here
def objective_fn(objective: str, x: dict, solver: Any, providers: numpy.ndarray, ors: numpy.ndarray, days: numpy.ndarray,
                 avail: dict, assigned: dict, cost: dict, specialty1_cost: dict, newPeriod: list):

    if objective == 'avg_pain':
        z = solver.NumVar(0, solver.infinity(), f'z')
        # objective
        # minimize average pain per SiteA-Room day
        for i in providers:
            room_days = sum([min(avail[i, j], 1) for j in days])
            if room_days > 1:
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) <= z * room_days)

        # minimize objective function
        solver.Minimize(z)

    elif objective == 'min_tot_pain_span':
        z_min = solver.NumVar(0, solver.infinity(), f'z_min')
        z_max = solver.NumVar(0, solver.infinity(), f'z_max')

        for i in providers:
            room_days = sum([min(avail[i, j], 1) for j in days])
            if room_days > 0:
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) <= z_max)
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) >= z_min)

        solver.Minimize(z_max - z_min)

    elif objective == 'max_pain':
        z = solver.NumVar(0, solver.infinity(), f'z')
        for i in providers:
            room_days = sum([min(avail[i, j], 1) for j in days])
            if room_days > 1:
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) <= z * room_days)
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) <= 51)

        solver.Minimize(z)

    elif objective == "max_pain1":
        z = solver.NumVar(0, 1000, f'z')
        z_max = solver.NumVar(0, 1000, f'z_max')
        z_high = solver.NumVar(0, 30, f'z_high')
        for i in providers:
            room_days = sum([min(avail[i, j], 1) for j in days])
            if room_days > 0:
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) <= z * room_days)
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors if
                                        newPeriod[0] <= j <= newPeriod[1]]) + specialty1_cost[i]) <= z_max)
                solver.Add(solver.Sum(
                    [x[i, j, k] for k in ors[9:20] for j in days if newPeriod[0] <= j <= newPeriod[1]]) <= z_high)
        solver.Minimize(z + 0.05 * z_max + z_high)

    elif objective == "max_pain2":
        solver.Minimize(solver.Sum([(solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors])
                                     + specialty1_cost[i]) / sum([avail[i, j] for j in days])
                                    for i in providers if sum([avail[i, j] for j in days]) > 1]))

    elif objective == "max_pain3":
        z_mean = solver.NumVar(0, 6, f'z_mean')
        z = {}
        z_plus = {}
        z_minus = {}
        p_count = 0
        room_days = {}
        for i in providers:
            room_days[i] = sum([min(avail[i, j], 1) for j in days])
            if room_days[i] > 1:
                z[i] = solver.NumVar(0, 10, f'z_{i}')
                z_plus[i] = solver.NumVar(0, 25, f'z_plus[{i}]')
                z_minus[i] = solver.NumVar(0, 25, f'z_minus[{i}]')
                p_count += 1
                solver.Add(solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                           specialty1_cost[i] == z[i] * room_days[i])
        solver.Add(solver.Sum([z[i] for i in providers if room_days[i] > 1]) == z_mean * p_count)
        for i in providers:
            if room_days[i] > 1:
                solver.Add(z[i] - z_mean == z_plus[i] - z_minus[i])
        solver.Minimize(solver.Sum([z_plus[i] + z_minus[i] for i in providers if room_days[i] > 1]))

    elif objective == 'max_pain4':
        room_days = {}
        z_avg = {}
        for i in providers:
            room_days[i] = sum([min(avail[i, j] + sum([assigned[i, j, k] for k in ors]), 1) for j in days])
            if room_days[i] > 0:
                z_avg[i] = solver.NumVar(0, 100, f'z_avg[{i}]')
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) == z_avg[i] * room_days[i])
        solver.Minimize(solver.Sum([z_avg[i] for i in providers if room_days[i] > 0]))

    elif objective == 'SD_max_pain4':
        room_days = {}
        z_avg = {} # initiate the average pain of a provider
        totalAvgCost = solver.NumVar(0, solver.infinity(), 'TotalOfAvg')
        AvgOfAvgCost = solver.NumVar(0, solver.infinity(), 'AvgOfAvgCost')
        totalDiffPlus = solver.NumVar(0, solver.infinity(), 'totalDiffPlus')
        totalDiffMinus = solver.NumVar(0, solver.infinity(), 'totalDiffMinus')
        totalNumOfProviders = 0
        for i in providers:
            totalNumOfProviders = totalNumOfProviders +1
            room_days[i] = sum([min(avail[i, j] + sum([assigned[i, j, k] for k in ors]), 1) for j in days])
            if room_days[i] > 0:
                z_avg[i] = solver.NumVar(0, 100, f'z_avg[{i}]')
                solver.Add((solver.Sum([cost[k] * (x[i, j, k] + assigned[i, j, k]) for j in days for k in ors]) +
                            specialty1_cost[i]) == z_avg[i] * room_days[i])
        #solver.Add(totalAvgCost == solver.Sum([z_avg[i] for i in providers if room_days[i] > 0]))

        solver.Add(AvgOfAvgCost == solver.Sum([z_avg[i] for i in providers if room_days[i] > 0])/totalNumOfProviders)
        #solver.
        #solver.Add(AvgOfAvgCost == totalAvgCost/totalNumOfProviders)
        #solver.Add(totalDiffPlus == solver.Sum([(z_avg[i] - AvgOfAvgCost) for i in providers if room_days[i] > 0 and z_avg[i] >= AvgOfAvgCost]))
        #solver.Add(totalDiffMinus == solver.Sum([(AvgOfAvgCost - z_avg[i]) for i in providers if room_days[i] > 0 and z_avg[i] <= AvgOfAvgCost]))
        #print(totalAvgCost)
        #solver.Minimize(totalDiffPlus)
        solver.Minimize(AvgOfAvgCost)
        #solver.Minimize(solver.Sum([z_avg[i] for i in providers if room_days[i] > 0]))

    else:
        z = {}
        raise ModuleNotFoundError(f"Objective function not implemented for type {objective}")
    return solver


def assignment(cost: dict, avail: dict, assigned: dict, specialty1_cost: dict, specialty2_assignment: dict, providers: numpy.ndarray,
               days: numpy.ndarray, ors: numpy.ndarray, high_cost_rooms: numpy.ndarray,
               objective: str, parttime: numpy.ndarray, newPeriod: list, no_call_assigned: dict, max_room: dict) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Solve the assignment problem given the input and return the assignment dataframe along with the dataframe for average pain per provider.
    :param newPeriod: Period of new assignment
    :param parttime: array of parrtime providers
    :param cost: cost of each task
    :param avail: if a task/or needs to be assigned
    :param assigned: if a task/or has already been assigned
    :param specialty1_cost: cost of specialty1 assignment
    :param specialty2_assignment: if an ob call is assigned
    :param providers: list of providers
    :param days: list of days
    :param ors: list of ors
    :param high_cost_rooms: list of high cost rooms
    :param objective: what pain is to be minimized ['avg_pain', 'max_pain', 'min_tot_pain_span']
    :return: final assignment dataframe and average pain per provider
    """
    # Instantiate a mixed-integer solver
    solver = pywraplp.Solver.CreateSolver('cbc')

    x = initialize_decision_variables(providers, days, ors, newPeriod, solver, assigned, avail)
    #print("--------------219-----------------")
    #print(x)
    solver = objective_fn(objective, x, solver, providers, ors, days, avail, assigned, cost, specialty1_cost, newPeriod)
    #print("--------------222-----------------")
    #print(solver)

    refX = {}


    # if no call assigned do not assign ors 7 or less
    for i, j in itertools.product(providers, days):
        if no_call_assigned[i, j] == 1:
            #solver.Add(solver.Sum([x[i, j, k] for k in ['SiteA - Room 1', 'SiteA - Room 2', 'SiteA - Room 3', 'SiteA - Room 4', 'SiteA - Room 5', 'SiteA - Room 6', 'SiteA - Room 7']]) == 0)
            solver.Add(solver.Sum([x[i, j, k] for k in ROOM_LIST_1_TO_6]) == 0)

    # Deprecated in December 2020
    # # Each provider is assigned to max of 1 high cost rooms per month
    # for i, k in itertools.product(providers, ['SiteA - Room 1', 'SiteA - Room 3']):
    #     if k != 'SiteA - Room 2':
    #         solver.Add(solver.Sum([x[i, j, k] for j in days if (newPeriod[0] <= j <= newPeriod[1])]) <= 1)


    # each room is assigned to at max of one provider based on availability
    for j, k in itertools.product(days, ors[:20]):
        solver.Add(solver.Sum([x[i, j, k] + assigned[i, j, k] for i in providers])
                   <= max([avail[i, j] for i in providers]))


    for i, j in itertools.product(providers, days):
        if not (newPeriod[0] <= j <= newPeriod[1]):
            continue

        # Each provider is assigned to a room depending on the availability
        solver.Add(solver.Sum([x[i, j, k] for k in ors[:20]]) == avail[i, j])

        max_room_number = max_room[j]
        # if backup1 is assigned on day j then Room 7 is assigned on day j
        if assigned[i, j, Task.BACKUP1] == 1: # no problem for Jan
            if max_room_number >= 8:
                solver.Add(x[i, j, Task.ROOM_7] == avail[i, j])
                #print(x[i,j,'SiteA - Room 7'])
                if avail[i, j] == 1:
                     refX[i,j,Task.ROOM_7] = 1
                #refX[i,j,Task.ROOM_7] = 1
                #print(refX)
            #elif max_room_number > 2:
            elif max_room_number > 2:
                solver.Add(x[i, j, room(max_room_number)] == avail[i, j])
                if avail[i, j] == 1:
                     refX[i,j,Task.ROOM_7] = 1
                #refX[i, j, room(max_room_number)] = 1
                #print(refX)

        if assigned[i, j, Task.BACKUP2] == 1:
            if max_room_number >= 8:
                solver.Add(x[i, j, Task.ROOM_8] == avail[i, j])
                # having problem with the following code
                # if avail[i, j] == 1:
                #      refX[i,j,Task.ROOM_7] = 1
                refX[i, j, Task.ROOM_8] = 1
                #print(refX)

            elif max_room_number > 2:
                solver.Add(x[i, j, room(max_room_number)] == avail[i, j])
                refX[i, j, room(max_room_number)] = 1
                #print("343------reference X: {0}".format(refX))

        # if assigned[i, j, Task.BACKUP1] == 1:
        #     if max_room_number >= 8:
        #         solver.Add(x[i, j, 'SiteA - Room N1'] == avail[i, j])
        #     #elif max_room_number > 2:
        #     elif max_room_number > 2:
        #         solver.Add(x[i, j, f'SiteA - Room {max_room_number -1}'] == avail[i, j])
        #
        # if assigned[i, j, Task.BACKUP2] == 1:
        #     if max_room_number >= 8:
        #         solver.Add(x[i, j, 'SiteA - Room N2'] == avail[i, j])
        #     elif max_room_number > 2 and max_room_number == 7:
        #     #else:
        #         solver.Add(x[i, j, 'SiteA - Room N1'] == avail[i, j])
        #     elif max_room_number > 2:
        #         solver.Add(x[i, j, room(max_room_number)] == avail[i, j])

    # low number ors should be assigned first
    for j in days:
        if not (newPeriod[0] <= j <= newPeriod[1]):
            continue
        for idx, k in enumerate(ors[:19]):
            k_next = ors[idx + 1]
            solver.Add(solver.Sum([x[i, j, k] - x[i, j, k_next] for i in providers]) >= 0)

    high_pain = HIGH_COST_TASKS

    for i in providers:
        # if the provider is part-time, then assign high number ORs
        if i in parttime:
            # was like this
            #solver.Add(solver.Sum([x[i, j, k] for j in days for k in ['SiteA - Room 1', 'SiteA - Room 3', 'SiteA - Room 4',
            #                                                          'SiteA - Room 5', 'SiteA - Room 6', 'SiteA - Room 7']]) == 0)
            # ideally the part-time providers should be assigned with a task in the range of Room 6 ~ Room 8
            solver.Add(solver.Sum([x[i, j, k] for j in days for k in PARTTIME_EXCLUDED]) == 0)

        # # if Specialty2 assignment then don't assign SiteA Room 1 (check with Ron)
        # if specialty2_assignment[i] > 1:
        #     solver.Add(solver.Sum([x[i, j, 'SiteA - Room 1'] for j in days]) == 0)

        # if backup1 assigned on day j then highest numbered room on the next day
        # this comment should not be here
        # this is dealing with the weekday and weekends
        #print(days)
        for idx, j in enumerate(days[:-1]):
            #print(idx)
            #print(j)
            #print(j.isoweekday())
            j_next = days[idx + 1]
            if j.isoweekday() == 5:
                if len(days) >= idx + 3:
                    j_next = days[idx + 3]
            elif j.isoweekday() == 6:
                if len(days) >= idx + 2:
                    j_next = days[idx + 2]
            elif j.isoweekday() == 7:
                if len(days) >= idx + 1:
                    j_next = days[idx + 1]

            if (not (newPeriod[0] <= j_next <= newPeriod[1])) or max_room[j_next] <= 0:
                continue
            # if high cost room is assigned on day j, j+1 should be high numbered rooms
            if sum([assigned[i, j, k] + assigned[i, j_next, k] for k in high_pain]) > 1:
                continue
            solver.Add(solver.Sum([x[i, j, k] + x[i, j_next, k] + assigned[i, j, k] for k in high_pain]) <= 1)
            solver.Add(solver.Sum([x[i, j, k] + x[i, j_next, k] + assigned[i, j_next, k] for k in high_pain]) <= 1)

    for idx, j in enumerate(days[:-1]):
        j_next = days[idx + 1]
        if j.isoweekday() == 5:
            if len(days) >= idx + 3:
                j_next = days[idx + 3]
        elif j.isoweekday() == 6:
            if len(days) >= idx + 2:
                j_next = days[idx + 2]
        elif j.isoweekday == 7:
            if len(days) >= idx + 1:
                j_next = days[idx + 1]

        if (not (newPeriod[0] <= j_next <= newPeriod[1])) or max_room[j_next] <= 0:
            continue

        max_room_number = max_room[j_next]
        #print("-----------330-----------")
        print(j_next)
        print(max_room_number)
        MAX_ROOM = room(max_room_number)



        # the following was 1st
        ii = [i for i in providers if assigned[i, j, Task.BACKUP1] == 1]
        #print(ii)
        #print(ii[0])
        #print(max_room_number)
        #print(j_next)
        #print(len(ii))
        #print(avail[ii[0], j_next])
        #print(max_room_number)
        if len(ii) > 0 and avail[ii[0], j_next] > 0 and max_room_number >= 9:
            #print(ii)
            #print(j_next)
            #print(max_room_number)
            i = ii[0]
            #print(i)
            #print(j_next)
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #i = ii[0]
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 7 <= max_room_number <= 8:
            i = ii[0]
            print("525------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #i = ii[0]
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        #i = ii[0]
                        #print("558------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)
                    else:
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)
                        if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                            #i = ii[0]
                            # print("558------reference X: {0}".format(refX))
                            solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                            refX[i, j_next, MAX_ROOM] = 1
                            max_room_number -= 1
                            MAX_ROOM = room(max_room_number)

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 3 <= max_room_number <= 6:
            i = ii[0]
            #print(MAX_ROOM)
            #print(max_room_number)
            #print("524------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("565------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        #print("558------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)


        # the following was 2nd
        # need to double check here
        ii = [i for i in providers if assigned[i, j, Task.EVE_SHIFT1] == 1]
        #print("531------ii: {0}".format(ii))
        #print("532------avail[ii[0], j_next]: {0}".format(avail[ii[0], j_next]))
        if len(ii) > 0 and avail[ii[0], j_next] > 0 and max_room_number >= 9:
            i = ii[0]
            # print(ii)
            # print(max_room_number)
            # print("535------j_next: {0}".format(j_next))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                print("695------print something here")
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    print("697------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 7 <= max_room_number <= 8:
            i = ii[0]
            print("601------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            # something is wrong here (12/14/2020)
            # else:
            #     max_room_number -= 1
            #     MAX_ROOM = room(max_room_number)
            #     print("695------print something here")
            #     if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
            #         print("697------reference X: {0}".format(refX))
            #         solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
            #         refX[i, j_next, MAX_ROOM] = 1
            #         max_room_number -= 1
            #         MAX_ROOM = room(max_room_number)


        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 3 <= max_room_number <= 6:
            i = ii[0]
            #print(MAX_ROOM)
            #print(max_room_number)
            #print("524------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    # print("501------reference X: {0}".format(refX))
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)


        # the following was 3rd
        # kept for the record
        ii = [i for i in providers if assigned[i, j, Task.EVE_SHIFT2] == 1]
        #print(ii)
        if len(ii) > 0 and avail[ii[0], j_next] > 0 and max_room_number >= 9:
            print("661------the 'SiteA - EveShift2 12p' >=9 is triggered: {0}".format(""))
            i = ii[0]
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                solver.Add(x[i, j_next, MAX_ROOM ] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                #print("501------reference X: {0}".format(refX))
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                print("695------print something here")
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    print("697------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 7 <= max_room_number <= 8:
            i = ii[0]
            print("681------keys in reference X: {0}".format((i, j_next, MAX_ROOM)))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                print("688------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                print("695------print something here")
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    print("697------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    print("696------print something else")
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        print("700------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)
                    else:
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)
                        print("707------print something else")
                        if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                            print("711------reference X: {0}".format(refX))
                            solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                            refX[i, j_next, MAX_ROOM] = 1
                            max_room_number -= 1
                            MAX_ROOM = room(max_room_number)

                        else:
                            max_room_number -= 1
                            MAX_ROOM = room(max_room_number)
                            print("713------print something else")
                            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                                # print("print something")
                                print("726------reference X: {0}".format(refX))
                                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                                refX[i, j_next, MAX_ROOM] = 1
                                max_room_number -= 1
                                MAX_ROOM = room(max_room_number)
                            else:
                                max_room_number -= 1
                                MAX_ROOM = room(max_room_number)
                                print("733------print something else")
                                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                                    print("735------reference X: {0}".format(refX))
                                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                                    refX[i, j_next, MAX_ROOM] = 1
                                    max_room_number -= 1
                                    MAX_ROOM = room(max_room_number)


        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 3 <= max_room_number <= 6:
            i = ii[0]
            # print(MAX_ROOM)
            # print(max_room_number)
            # print("524------keys in reference X: {0}".format(refX.keys()))
            # print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("527------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("739------a: {0}".format(a))
            # print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #i = ii[0]
                #print("533------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #print("541------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        #print("549------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1
                        max_room_number -= 1
                        MAX_ROOM = room(max_room_number)


        # the following was 4th : 'SiteA - Backup2'
        ii = [i for i in providers if assigned[i, j, Task.BACKUP2] == 1]
        # print("613------ii: {0}".format(ii))
        # print("614------len(ii): {0}".format(len(ii)))
        # print("615------avail[ii[0], j_next]: {0}".format(avail[ii[0], j_next]))
        # print("616------max_room_number: {0}".format(max_room_number))
        if len(ii) > 0 and avail[ii[0], j_next] > 0 and max_room_number >= 9:
            i = ii[0]
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        #print("549------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 7 <= max_room_number <= 8:
            i = ii[0]
            print("788------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    print("808------print something else")
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        print("810------reference X: {0}".format(refX))
                        #solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        # we may want to check here (12/14/2020)
                        solver.Add(
                            x[i, j_next, MAX_ROOM] + x[i, j_next, room(max_room_number-1)] == avail[i, j_next]
                        )
                        refX[i, j_next, MAX_ROOM] = 1
        #             else:
        #                 max_room_number -= 1
        #                 MAX_ROOM = room(max_room_number)
        #                 if checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
        #                     i = ii[0]
        #                     # print("558------reference X: {0}".format(refX))
        #                     solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
        #                     refX[i, j_next, MAX_ROOM] = 1

        elif len(ii) > 0 and avail[ii[0], j_next] > 0 and 3 <= max_room_number <= 6:
            #print(MAX_ROOM)
            #print(max_room_number)
            print("784------keys in reference X: {0}".format(refX.keys()))
            #print("525------keys in reference X: {0}".format(type(refX.keys())))
            #print("536------the key to check: {0}".format((i, j_next, MAX_ROOM)))
            #a = checkKey(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM))
            #print("538------a: {0}".format(a))
            #print("524------reference X: {0}".format(checkKey(refX, refX[i, j_next, MAX_ROOM])))
            i = ii[0]
            if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                #print("542------reference X: {0}".format(refX))
                solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                refX[i, j_next, MAX_ROOM] = 1
            else:
                max_room_number -= 1
                MAX_ROOM = room(max_room_number)
                #i = ii[0]
                if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                    #print("550------reference X: {0}".format(refX))
                    solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                    refX[i, j_next, MAX_ROOM] = 1
                else:
                    max_room_number -= 1
                    MAX_ROOM = room(max_room_number)
                    if checkIfInRefX(providers, refX, [i, j_next, MAX_ROOM], (i, j_next, MAX_ROOM)) == 0:
                        #i = ii[0]
                        #print("558------reference X: {0}".format(refX))
                        solver.Add(x[i, j_next, MAX_ROOM] == avail[i, j_next])
                        refX[i, j_next, MAX_ROOM] = 1

        # for i, j in itertools.product(providers, days):
        #     if not (newPeriod[0] <= j <= newPeriod[1]):
        #         continue
        #
        #     # Each provider is assigned to a room depending on the availability
        #     solver.Add(solver.Sum([x[i, j, k] for k in ors[:20]]) == avail[i, j])
        #
        #     max_room_number = max_room[j]
        #     # if backup1 is assigned on day j then Room 7 is assigned on day j
        #     if assigned[i, j, 'SiteA - Room 7'] == 1:
        #         if max_room_number >= 8:
        #             solver.Add(x[i, j, 'SiteA - Room N'] == avail[i, j])
        #
        #     if assigned[i, j, 'SiteA - Room 8'] == 1:
        #         if max_room_number >= 8:
        #             solver.Add(x[i, j, 'SiteA - Room N'] == avail[i, j])

        continue

    # solve the optimization problem
    solver_status = solver.Solve()
    logger.info(f"Solver status: {solver_status}")
    logger.info(f"Time = {solver.WallTime()} milliseconds")
    logger.info(f"Optimal objective value: {solver.Objective().Value()}")

    # print(assigned)
    # for (i,j,k) in x:
    #     if k == 'SiteA - Room 7':
    #         print((i,j,k))
    #print(x)
    #print(assigned)
    #print(days)
    #print(providers)
    solution = get_sol(x, assigned, days, providers)
    #print(solution)

    new_pain = get_optimal_pain(x, providers, days[numpy.logical_and(days <= newPeriod[1], days >= newPeriod[0])], ors, cost, specialty1_cost, avail, assigned)
    total_pain = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
    return solution, new_pain, total_pain


def check_avail(x: str) -> bool:
    """
    Get the days of availability.
    Only days which consists of SiteA - Room, SiteA - Coordination and Late assignments are considered.
    :param x: assignment string from the grid file
    :return: available or not
    """
    if GridValue.ROOM in x:
        return True
    elif GridValue.NO_CALL in x:
        return True
    else:
        return False


def check_assigned(x: Any, or_assigned: dict, ors: numpy.ndarray) -> dict:
    """
    Check if duty is already assigned. Currently only Coordination and Late (for first couple of days) are assigned.
    Ignoring Specialty2 and Specialty1 assignments
    :param ors: list of ors
    :param or_assigned: dictionary with or # as key and value as 0 or 1
    :param x: assignment string from the grid file
    :return: if already assigned or not
    """
    out = or_assigned.copy()
    for i in x:
        if isinstance(i, float) and numpy.isnan(i):
            continue
        if i in ors:
            out[i] = 1
        elif GridValue.COORDINATOR in i:
            out[Task.LEAD] = 1
    return out


def clean_grid(grid: pd.DataFrame, tasks: pd.DataFrame, newPeriod: list) -> Tuple[pd.DataFrame, int]:
    """
    Keep relevant providers and change the format of the dataframe from wide to long
    :param newPeriod: Duration of assignment
    :param tasks: task dataframe
    :param grid: input general assignment
    :return: cleaned up dataframe of the assignment. ready for use in the assignment model
    """
    start, end = newPeriod
    grid = grid.melt(id_vars='ProviderID', var_name='Date', value_name='Assignment')
    new_grid = grid.groupby(["ProviderID", "Date"])['Assignment'].apply(lambda x: list(set(x))).reset_index()
    new_grid['Date'] = pd.to_datetime(new_grid.Date).dt.date
    new_grid['avail'] = [1 * sum(check_avail(s) for s in i if type(s) == str) for i in new_grid.Assignment]
    n_room = new_grid.groupby(['Date'])['avail'].sum().max()
    ors = tasks.Task.values
    rooms_assigned = dict(zip(ors, [0] * ors.shape[0]))
    new_grid['assigned'] = new_grid.Assignment.apply(lambda x: check_assigned(x, rooms_assigned, ors))
    new_grid['specialty2_clinic_assigned'] = new_grid.Assignment.apply(lambda x: any((DetectionKey.SPECIALTY2_CLINIC in s) for s in x if type(s) == str))
    new_grid['specialty2_assigned'] = new_grid.Assignment.apply(lambda x: any((DetectionKey.SPECIALTY2_ONCALL in s) for s in x if type(s) == str))
    new_grid['sitec_assigned'] = new_grid.Assignment.apply(lambda x: any((DetectionKey.SITEC in s) for s in x if type(s) == str))
    new_grid['specialty1_assigned'] = new_grid.Assignment.apply(lambda x: any((DetectionKey.SPECIALTY1 in s) for s in x if type(s) == str))
    new_grid['specialty3_assigned'] = new_grid.Assignment.apply(lambda x: any((DetectionKey.SPECIALTY3 in s) for s in x if type(s) == str))
    new_grid['no_call_assigned'] = new_grid.Assignment.apply(lambda x: any((GridValue.NO_CALL in s) for s in x if type(s) == str))
    new_grid['uhor_count'] = new_grid.Assignment.apply(lambda x: any((GridValue.ROOM == s or GridValue.NO_CALL == s or GridValue.ROOM8 == s) for s in x if type(s) == str))
    return new_grid, n_room


def get_avail_assigned(grid: pd.DataFrame) -> Tuple[dict, dict]:
    """
    Given the cleaned grid find which provider has availability for SiteA Room on which days.
    :param grid: cleaned dataframe of relevant providers and relevant ors
    :return: two dictionaries, one of availability and one of pre assigned slots
    """
    avail = grid[['ProviderID', 'Date', 'avail']].pivot_table(index='ProviderID', columns='Date',
                                                              aggfunc='max').stack().to_dict()['avail']
    out_assigned = dict()
    assigned = grid[['ProviderID', 'Date', 'assigned']].pivot_table(index='ProviderID', columns='Date',
                                                                    aggfunc='max').stack().to_dict()['assigned']
    for key, val in assigned.items():
        for k, v in val.items():
            out_assigned[key + (k,)] = v
    return avail, out_assigned


def main(arg: argparse.Namespace) -> None:
    df_task = read_file(arg.task)
    df_grid = read_file(arg.grid)
    df_partTime = read_file(arg.parttime).ProviderID.values

    # keep relevant tasks
    high_cost_rooms = numpy.array([Task.ROOM_1, Task.ROOM_3])

    # clean the grid
    df_grid, N_ROOM = clean_grid(df_grid, df_task, args.newPeriod)
    df_dates = df_grid.Date.drop_duplicates()
    df_dates_sort = df_dates.sort_values()
    provider_ids = df_grid.ProviderID.unique()
    ob_specialty1_assignment = df_grid.groupby("ProviderID")[
        ["specialty1_assigned", "specialty2_assigned", "sitec_assigned", "specialty3_assigned"]].sum().reset_index()
    specialty1_cost = dict(zip(ob_specialty1_assignment.ProviderID, arg.specialty1cost * ((ob_specialty1_assignment.specialty1_assigned >= 1) |
                                                                           (ob_specialty1_assignment.sitec_assigned >= 3) |
                                                                           (ob_specialty1_assignment.specialty3_assigned >= 3))))
    specialty2_assignment = dict(zip(ob_specialty1_assignment.ProviderID, ob_specialty1_assignment.specialty2_assigned))
    #print(specialty2_assignment)
    no_call_assigned = df_grid.groupby(["ProviderID", "Date"])[['no_call_assigned']].sum().reset_index()
    no_call_assigned = dict(
        zip(tuple(zip(no_call_assigned.ProviderID, no_call_assigned.Date)), no_call_assigned.no_call_assigned))
    max_rooms = df_grid.groupby(['Date'])[['uhor_count']].sum().reset_index()
    max_rooms = dict(zip(max_rooms.Date, max_rooms.uhor_count))
    print("957------max_rooms: {0}".format(max_rooms))

    # get availability
    avail, assigned = get_avail_assigned(df_grid)

    # get cost
    cost = dict(zip(df_task.Task, df_task.Cost))

    # solve assignment problem
    solution, opt_pain, tot_pain = assignment(cost, avail, assigned, specialty1_cost, specialty2_assignment, provider_ids,
                                              df_dates_sort.values, df_task.Task.values, high_cost_rooms,
                                              arg.objective, df_partTime, args.newPeriod, no_call_assigned, max_rooms)
    solution.dropna(axis=0, how='all', inplace=True)
    opt_pain.dropna(axis=0, how='all', inplace=True)
    tot_pain.dropna(axis=0, how='all', inplace=True)
    write_output({'assignment': solution, 'avg_pain': opt_pain, 'old_new_pain': tot_pain}, arg.output)
    return None


def evaluate_grid(ARGS):
    # read final assigned grid and task file for pain
    df_grid = read_file(ARGS.assignedGrid)
    df_task = read_file(ARGS.task)
    df_partTime = read_file(ARGS.parttime).ProviderID.values

    df_grid, N_ROOM = clean_grid(df_grid, df_task)
    df_dates = df_grid.Date.drop_duplicates()
    provider_ids = df_grid.ProviderID.unique()
    ob_specialty1_assignment = df_grid.groupby("ProviderID")[["specialty1_assigned", "specialty2_assigned",
                                                         "sitec_assigned", "specialty3_assigned"]].sum().reset_index()
    specialty1_cost = dict(zip(ob_specialty1_assignment.ProviderID, ARGS.specialty1cost * ((ob_specialty1_assignment.specialty1_assigned >= 1) |
                                                                            (ob_specialty1_assignment.sitec_assigned >= 3) |
                                                                            (ob_specialty1_assignment.specialty3_assigned >= 3))))
    specialty2_assignment = dict(zip(ob_specialty1_assignment.ProviderID, ob_specialty1_assignment.specialty2_assigned))

    # get availability
    avail, assigned = get_avail_assigned(df_grid)

    # get cost
    cost = dict(zip(df_task.Task, df_task.Cost))
    df = get_optimal_pain(None, provider_ids, df_dates.values, df_task.Task.values, cost, specialty1_cost, avail, assigned)
    df.to_csv(ARGS.output)


if args.action == "assign":
    main(args)
elif args.action == "evaluate_grid":
    evaluate_grid(args)