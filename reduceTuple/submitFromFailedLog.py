#! /usr/bin/env python

#
# This little script scans the logs and will resubmit failed jobs
# (i.e. those not containing 'finished' or 'Finished' in their log)
#
import argparse, os
from time import time
argParser = argparse.ArgumentParser(description = "Argument parser")
argParser.add_argument('--logLevel', action='store',      default='INFO', help='Log level for logging', nargs='?', choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'TRACE'])
argParser.add_argument('--runLocal', action='store_true', default=False,  help='Use local resources instead of Cream02')
argParser.add_argument('--dryRun',   action='store_true', default=False,  help='Do not launch subjobs')
argParser.add_argument('--select',   nargs='*', type=str, default=[],     help='Resubmit only commands containing all strings given here')
argParser.add_argument('--tolerant', action='store_true', default=False,  help='do not consider e.g. a missing tuple file a reason for resubmit')
argParser.add_argument('--printPaths', action='store_true', default=False,  help='print the paths to the failed log files, for quick opening')
argParser.add_argument('--cleanFolders',   action='store_true', default=False,  help='Remove empty folders')
argParser.add_argument('--age',   action='store', default=999., type=float,  help='ignore logs older than x days')
argParser.add_argument('--subAlreadyExists',   action='store_true', default=False,  help='submit/show jobs that are done because the output already existed')
args = argParser.parse_args()

from topSupport.tools.logger import getLogger
log = getLogger(args.logLevel)

# Get paths to all logs and analyze the files
# def getLogs(logDir):
#   for topDir, subDirs, files in os.walk(logDir):
#     if not len(files) and not len(subDirs):
#       if args.cleanFolders:
#         os.rmdir(topDir)
#     else:
#       for f in files:
#         yield os.path.join(topDir, f)

def getLogs(logDir):
  for topDir, subDirs, files in os.walk(logDir):
    for f in files:
      yield os.path.join(topDir, f)

time_now = time()
agesec = args.age* 60*60*24

jobsToSubmit = []
for logfile in getLogs('./log'):
  if not logfile[-4:] == '.err': continue
  if (time_now - os.path.getmtime(logfile)) > agesec: continue
  finished  = False
  rootError = False
  command   = None
  miscProblem = False
  alreadyExists = False
  with open(logfile) as logf:
    for line in logf:
      if 'Finished transferring output files' in line: continue # condor uses the word Finished as well, ignore that...
      if 'SysError in <TFile::ReadBuffer>' in line: rootError = True
      if 'Error in <TChain::LoadTree>' in line:     rootError = True
      if 'Finished' in line or 'finished' in line:  finished  = True
      if 'valid outputfile already exists' in line: alreadyExists = True
      if 'Could not produce all plots' in line:     
        finished = True
        miscProblem = True
      if 'Command:' in line:                        command   = line.split('Command: ')[-1].rstrip()
  if not command: 
    log.info('no valid command??')
    log.info(logfile)
    continue
  if args.select and not all(command.count(sel) for sel in args.select): continue
  if (not finished or ((rootError or miscProblem) and not args.tolerant)) and command: jobsToSubmit.append(( command + (' --overwrite' if ((command.count('reduceTuple') or command.count('chargeMisIDReduce')) and not command.count('--overwrite')) else ''), logfile))
  if alreadyExists and args.subAlreadyExists:
    log.info('already exists case: ' + logfile)
    if command: jobsToSubmit.append((command + ' --overwrite', logfile))


# Update latest git status before resubmitting
from topSupport.tools.helpers import updateGitInfo
updateGitInfo()


# Resubmit the failed jobs
from topSupport.tools.jobSubmitter import launchLocal, launchCream02, launchCondor
from datetime import datetime
for i, (command, logfile) in enumerate(jobsToSubmit):
  if args.dryRun:
    log.info('Dry-run: ' + command)
    if args.printPaths:
      log.info('log location: ' + logfile)
      log.info('----------------------------------------------------------------------------')
  else:
    os.remove(logfile)
    if args.runLocal: launchLocal(command, logfile)
    else:
      # launchCream02(command, logfile, checkQueue=(i%100==0), wallTime='168', jobLabel='RE', cores=8 if logfile.count("calcTriggerEff") else 1) # TODO: ideally extract walltime, cores,... from the motherscript
      launchCondor(command, logfile.replace('.err', '.log'), checkQueue=(i%100==0), wallTime='168', jobLabel='RE', cores=8 if logfile.count("calcTriggerEff") else 1) # TODO: ideally extract walltime, cores,... from the motherscript
