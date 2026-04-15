import argparse
import logging
import os
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(level=os.environ.get('LOGLEVEL', 'DEBUG'))
logger = logging.getLogger("SchedulingApp")

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--grid", help="path of the csv file with the provider availability", type=Path,
                    default="data/grid.csv", nargs='+')
parser.add_argument("--newPeriod", help="path of the csv file with the provider assignment for previous months",
                    type=date.fromisoformat, default=None, nargs='+')
parser.add_argument("--task", help="Path of the cost/pain file", type=Path, default='data/task.csv')
parser.add_argument("--parttime", help="Path of the file with parttime provider ids", type=Path,
                    default='data/parttime.csv')
parser.add_argument("--output", help="Path of the assignment output file", type=Path, default='data/assignment.xlsx')
parser.add_argument("--objective", help="Provide the type of objective", type=str,
                    choices=['avg_pain', 'max_pain', 'max_pain1', 'min_tot_pain_span', 'max_pain2', 'max_pain3', 'max_pain4', 'SD_max_pain4'], default='avg_pain')
parser.add_argument("--specialty1cost", help="fixed Specialty2 pain per month", type=int, default=5)
parser.add_argument("--action", help="Solve the assignment problem", default='assign', type=str,
                    choices=['assign', 'evaluate_grid'])
#parser.add_argument("--evaluate_grid", help="Solve the assignment problem", default='assign', type=str,
#                    choices=['assign', 'evaluate_grid'])
args = parser.parse_args()
