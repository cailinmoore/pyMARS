import os, sys, argparse
import cantera as ct
os.environ['Cantera_Data'] =os.getcwd()
from create_trimmed_model import trim
from convert_chemkin_file import convert
import soln2ck
import soln2cti
from autoignition_module import run_sim
from get_rate_data import get_rates
from drg import make_graph
from drg_loop_control import drg_loop_control
from drgep_loop_control import drgep_loop_control
from autoignition_loop_control import autoignition_loop_control
from drgep import make_graph_drgep
from drgep import run_drgep
import numpy as np

def trim_drgep(args, solution_object):           
	"""
    Function to run the drgep method for model reduction

    Parameters
    ----------
    solution_object: ct._Solutuion object
	An object that represents the solution to be trimmed. 
    args: args object
	An object that contains the following:
    file:
        Input mechanism file (ex. file='gri30.cti')
    species:
        Species to eliminate (ex. species='H, OH')
    thermo:
        Thermo data file if Chemkin format (ex. thermo= 'thermo.dat')
    transport:
        Transport data file if Chemkin format
    plot:
        plot ignition curve (ex. plot='y')
    points:
        print ignition point and sample range (ex. points='y')
    writecsv:
        write data to csv (ex. writecsv='y')
    writehdf5:
        write data to hdf5 (ex. writehdf5='y')
    run_drg:
        Run DRG model reduction
    run_drgep:
	Run drgep model.
    error:
	Maximum ammount of error allowed. 
    keepers: list of strings
	The string names of the species that should be kept in the model no matter what.
    targets: list of strings
	The string names of the species that should be used as target species.

	"""

	if args.target == 0: #If the target species are not specified, puke and die.
		print "Please specify a target species."
		exit()
	done = [] #Singleton to hold wether or not any more species can be cut from the simulation.  
	done.append(False)
	threshold = .1 #Starting threshold value
	error = [0.0] #Singleton to hold the error value of the previously ran simulation.
	try:
		os.system('rm mass_fractions.hdf5')
	except Exception:
		pass
	
	args.multiple_conditions = True
	detailed_result = autoignition_loop_control(solution_object, args) #The simulation needs to be ran to make the mass_fractions file which has the info to calucalte edge weights I think?
	detailed_result.test.close()
	ignition_delay_detailed = np.array(detailed_result.tau_array)
	rate_edge_data = get_rates('mass_fractions.hdf5', solution_object) #Get edge weight calculation data. 
	max_dic = make_graph_drgep(solution_object, rate_edge_data, args.target) #Make the graph
	
	print "Testing for starting threshold value"
	drgep_loop_control(solution_object, args, error, threshold, done, max_dic) #Trim the solution at that threshold and find the error.
	while error[0] > args.error: #While the error for trimming with that threshold value is greater than allowed.
		threshold = threshold / 10 #Reduce the starting threshold value and try again.
		drgep_loop_control(solution_object, args, error, threshold, done, max_dic)
	
	print("Starting with a threshold value of " + str(threshold))
	sol_new = solution_object
	past = 0 #An integer representing the error introduced in the past simulation.  
	done[0] = False
        max_error = 0
	while not done[0]: #Run the simulation until nothing else can be cut. 
        	sol_new = drgep_loop_control( solution_object, args, error, threshold, done, max_dic) #Trim at this threshold value and calculate error.
                if args.error > error[0] and error[0] > max_error: #If a new max errow without exceeding what is allowed is reached, save those values.  
                        max_t = threshold
			max_error = error[0]
		if (past == error[0]): #If error wasn't increased, increase the threshold at a higher rate. 
			threshold = threshold + .04
		past = error[0]
        	threshold = threshold + .01
        
        print "\nGreatest result: "
        sol_new = drgep_loop_control( solution_object, args, error, max_t, done, max_dic)
	os.system('rm production_rates.hdf5')
	os.system('rm mass_fractions.hdf5')
	drgep_trimmed_file = soln2cti.write(sol_new) #Write the solution object with the greatest error that isn't over the allowed ammount.
	try:
		os.system('rm production_rates.hdf5')
	except Exception:
		pass
