import SkyNEt.modules.Evolution as Evolution
import SkyNEt.modules.SaveLib as SaveLib
import kmc_dopant_networks as kmc_dn
import kmc_dopant_networks_utils as kmc_dn_utils
import numpy as np
import matplotlib.pyplot as plt
import config_boolean_logic as config
import time


cf = config.experiment_config()

genePool = Evolution.GenePool(cf)

#%% System setup
xdim = 1
ydim = 1
layout = cf.layout
# Load layouts
acceptor_layouts = np.load('acceptor_layouts.npy')
donor_layouts = np.load('donor_layouts.npy')
if(cf.layoutsize == 10):
    acceptor_layouts = np.load('acceptor_layouts_10.npy')
    donor_layouts = np.load('donor_layouts_10.npy')
if(cf.layoutsize == 20):
    acceptor_layouts = np.load('acceptor_layouts_20.npy')
    donor_layouts = np.load('donor_layouts_20.npy')


# Define 8 electrodes
electrodes = np.zeros((8, 4))
electrodes[0] = [0, ydim/4, 0, 10]
electrodes[1] = [0, 3*ydim/4, 0, 0]
electrodes[2] = [xdim, ydim/4, 0, 10]
electrodes[3] = [xdim, 3*ydim/4, 0, 0]
electrodes[4] = [xdim/4, 0, 0, 10]
electrodes[5] = [3*xdim/4, 0, 0, 0]
electrodes[6] = [xdim/4, ydim, 0, 10]
electrodes[7] = [3*xdim/4, ydim, 0, 0]

if(cf.use_random_layout):
    kmc = kmc_dn.kmc_dn(cf.layoutsize, 
        cf.layoutsize//10, xdim, ydim, 0, electrodes=electrodes)
else:
    kmc = kmc_dn.kmc_dn(1, 0, xdim, ydim, 0, electrodes=electrodes)
    kmc.load_acceptors(acceptor_layouts[layout])
    kmc.load_donors(donor_layouts[layout])

# Parameters
kT = cf.kT
I_0 = cf.I_0
ab_R = cf.ab_R
prehops = cf.prehops
hops = cf.hops

kmc.kT = kT
kmc.I_0 = I_0
kmc.ab = ab_R*kmc.R

# Update constant quantities that depend on I_0 and ab
kmc.calc_E_constant()
kmc.calc_transitions_constant()

# Define input signals
P = [0, 1, 0, 1]
Q = [0, 0, 1, 1]
w = [1, 1, 1, 1]
kmc.electrodes[cf.output, 3] = 0

# Initialize arrays to save experiment
geneArray = np.zeros((cf.generations, cf.genomes, cf.genes))
outputArray = np.zeros((cf.generations, cf.genomes, 4*cf.avg))
fitnessArray = np.zeros((cf.generations, cf.genomes))
filepath = SaveLib.createSaveDirectory(cf.filepath, cf.name)
# Save experiment (also copies files)
SaveLib.saveExperiment(filepath,
                       geneArray = geneArray,
                       fitnessArray = fitnessArray,
                       outputArray = outputArray,
                       target = cf.target,
                       P = P,
                       Q = Q)

for i in range(cf.generations):
    geneArray[i] = genePool.pool
    for j in range(cf.genomes):
        if(i == 0 and j == 1):
            tic = time.time()
        if(i == 0 and j == 2):
            print(f'Estimated time: {(time.time()-tic)*cf.generations*cf.genomes/3600} h')
        # Set the Voltages
        for k in cf.controls:
            kmc.electrodes[k, 3] = cf.controlrange[0]*(1 - genePool.pool[j, k-3]) + genePool.pool[j, k-3]*cf.controlrange[1]

        fitness_list = []
        # Obtain device response
        output = np.zeros(4*cf.avg)
        for k in range(4):
            if(cf.evolve_input):
                kmc.electrodes[cf.P, 3] = P[k]*(cf.inputrange[0]*(1 - genePool.pool[j, -1]) + genePool.pool[j, -1]*cf.inputrange[1])
                kmc.electrodes[cf.Q, 3] = Q[k]*(cf.inputrange[0]*(1 - genePool.pool[j, -1]) + genePool.pool[j, -1]*cf.inputrange[1])
            else:
                kmc.electrodes[cf.P, 3] = P[k]*cf.inputrange
                kmc.electrodes[cf.Q, 3] = Q[k]*cf.inputrange

            kmc.update_V()
            if(cf.use_go):
                kmc.go_simulation(hops=0, prehops = cf.prehops,
                                  goSpecificFunction='wrapperSimulateRecord')
            else:
                kmc.python_simulation(prehops = prehops)
            for l in range(cf.avg):
                if(cf.use_go):
                    kmc.go_simulation(hops=cf.hops,
                                      goSpecificFunction='wrapperSimulateRecord')
                else:
                    kmc.python_simulation(hops = hops)
                output[k*cf.avg + l] = kmc.current[cf.output]
        outputArray[i, j] = output
        fitness_list.append(cf.Fitness(output, cf.target))

        genePool.fitness[j] = min(fitness_list)
        fitnessArray[i, j] = genePool.fitness[j]
    # Status print
    print("Generation nr. " + str(i + 1) + " completed")
    print("Highest fitness: " + str(max(genePool.fitness)))

    # Evolve to the next generation
    genePool.NextGen()

    # Save experiment
    SaveLib.saveArrays(filepath,
                           geneArray = geneArray,
                           fitnessArray = fitnessArray,
                           outputArray = outputArray,
                           target = cf.target,
                           P = P,
                           Q = Q)

domain = kmc_dn_utils.visualize_basic(kmc)
plt.figure()
plt.plot(output)
plt.show()
