import kmc_dopant_networks as kmc_dn
import kmc_dopant_networks_utils as kmc_utils
import dn_animation as anim

import numpy as np
import matplotlib.pyplot as plt

import copy
import random
import time
import math

class dn_search():
    def __init__(self, initial_dn, tests, xdim, ydim, x_start_resolution, y_start_resolution):
        '''
        =======================
        dn_search dopant network placement search class
        ======================= 
        This class is made for performing a search to find dopant_network (dn)
        placement that matches the test data.

        Input arguments
        ===============
        initial_dn; kmc_dn
            Instance of a kmc_dn class with initial dopant placements, which is used to create
            neighbouring kmc_dn instances to perform search.
        tests; list
            This is a list of tests, each test is a tuple, which contains electrode configuration
            and expected current(s)
        '''

        self.minimum_resolution = 0.01
        self.xdim = xdim
        self.ydim = ydim
        self.x_resolution = x_start_resolution
        self.y_resolution = y_start_resolution

        self.dn = initial_dn
        self.best_dn = self.dn
        self.tests = tests
        self.use_tests = len(tests)
        sum = 0
        for t in tests:
            for _ in t[1]:
                sum+=1
        self.N_tests = sum
        
        self.simulation_strategy = [
            {'func':"go_simulation",
             'args':{'hops':1000, 'goSpecificFunction':"wrapperSimulateProbability"},
             'expected_error':0.04,
             'threshold_error':0.005},
            {'func':"go_simulation",
             'args':{'hops':5000, 'goSpecificFunction':"wrapperSimulateRecord"},
             'expected_error':0.025,
             'threshold_error':0.005},
            {'func':"go_simulation",
             'args':{'hops':50000, 'goSpecificFunction':"wrapperSimulateRecord"},
             'expected_error':0.01,
             'threshold_error':0.002},
            {'func':"go_simulation",
             'args':{'hops':250000, 'goSpecificFunction':"wrapperSimulateRecord"},
             'expected_error':0.002,
             'threshold_error':0.0},
        ]
        self.setStrategy(0)
        self.error_func = self.average_cumulative_error
        self.initRandomPlacement()
        self.genetic_allowed_overlap = 65
        self.order_distance_function = dn_search.degreeDistance
        self.parallel = 0


    def init_search(self):
        self.validations = []

    def setUseTests(self, N):
        self.use_tests = N
        sum = 0
        for i in range(self.use_tests):
            for _ in self.tests[i]:
                sum+=1
        self.N_tests = sum
        

    def setStrategy(self, index):
        '''
        This changes the search strategy.
        :param index:
            index of the new search strategy. Strategy is taken form self.simulation_strategy array.
        '''
        self.current_strategy = index
        self.simulation_func = self.simulation_strategy[index]['func']
        self.simulation_args = self.simulation_strategy[index]['args']
        self.expected_error =  self.simulation_strategy[index]['expected_error']
        self.threshold_error =  self.simulation_strategy[index]['threshold_error']

    def evaluate_error(self, dn):
        '''
        Evaluates the error of som kmc_dn object, relative to the test set given in self.
        :param dn:
            Dopant network to be evaluated.
        :returns:
            score for the evaluation.
        '''
        diffs = []
        for j in range(self.use_tests):
            test = self.tests[j]
            electrodes = test[0]
            
            for i in range(len(electrodes)):
                dn.electrodes[i][3] = electrodes[i]
            dn.update_V()
            execpted_currents = test[1]
            getattr(dn, self.simulation_func)(**self.simulation_args)
            for index, current in execpted_currents:
                diff = math.fabs(dn.current[index]-current)
                diffs.append(diff)
        return self.error_func(diffs)

    def validate_error(self, dn):
        '''
        Validate the error of some dopant network object. In validation we use the last strategy, which is reserved for most accuracy.
        :param dn:
            Dopant network to be validated.
        :returns:
            score for the validation.
        '''
        diffs = []
        cur_strat = self.current_strategy
        self.setStrategy(len(self.simulation_strategy)-1)
        error = self.evaluate_error(dn)
        self.setStrategy(cur_strat)
        return error
        
    def average_cumulative_error(self, diffs):
        '''
        Legacy error function that was used in dopant placement search.
        :param diffs:
            list of differences from evaluated dopant network compared to expected values.
        :returns:
            result of the error function
        '''
        error = 0
        for diff in diffs:
            if diff > self.expected_error:
                error+=diff-self.expected_error
        return error / len(diffs)

    def initRandomPlacement(self):
        '''
        Inits random placement but within the given resolution.
        '''
        xInt = self.xdim / self.x_resolution
        yInt = self.ydim / self.y_resolution
        self.dn.xCoords = []
        self.dn.yCoords = []
        for i in range(self.dn.N):
            found = True
            x = 0
            y = 0
            while found:
                found = False
                x = np.random.randint(xInt)
                y = np.random.randint(yInt)
                for j in range(len(self.dn.xCoords)):
                    if self.dn.xCoords[j] == x and self.dn.yCoords[j] == y:
                        found = True
            self.dn.acceptors[i][0] = x * self.x_resolution 
            self.dn.acceptors[i][1] = y * self.y_resolution
            self.dn.xCoords.append(x * self.x_resolution)
            self.dn.yCoords.append(y * self.y_resolution)
        for i in range(self.dn.M):
            found = True
            x = 0
            y = 0
            while found:
                found = False
                x = np.random.randint(xInt)
                y = np.random.randint(xInt)
                for j in range(len(self.dn.xCoords)):
                    if self.dn.xCoords[j] == x and self.dn.yCoords[j] == y:
                        found = True
            self.dn.donors[i][0] = x * self.x_resolution 
            self.dn.donors[i][1] = y * self.y_resolution
            self.dn.xCoords.append(x * self.x_resolution)
            self.dn.yCoords.append(y * self.y_resolution)
        self.dn.initialize(dopant_placement=False, charge_placement=False)

    def yieldNeighbours(self):
        '''
            Yields neighbours of current state. Used by greedy and simulated annealing algorithms.
            This is the implementation for dopant placement search.
        '''
        N = self.dn.N + self.dn.M
        shifts = [(self.x_resolution, 0), (-self.x_resolution, 0), (0, self.y_resolution), (0, -self.y_resolution), (self.x_resolution, self.y_resolution), (-self.x_resolution, self.y_resolution), (-self.x_resolution, -self.y_resolution), (self.x_resolution, -self.y_resolution)]
        options = [(i, shifts[j][0], shifts[j][1]) for i in range(N) for j in range(len(shifts))]
        indexes = [x for x in range(len(options))]
        random.shuffle(indexes)
        for index in indexes:
            option = options[index]
            if option[0] < self.dn.N:
                dopant = self.dn.acceptors[option[0]]
                pos = (dopant[0]+option[1], dopant[1]+option[2])
            else:
                donor = self.dn.donors[option[0]-self.dn.N]
                pos = (donor[0]+option[1], donor[1]+option[2])
            if self.doesPositionFit(pos[0], pos[1]):
                newDn = kmc_dn.kmc_dn(self.dn.N, self.dn.M, self.xdim, 
                    self.ydim, 0, electrodes = self.dn.electrodes, 
                    acceptors=self.dn.acceptors, donors=self.dn.donors, copy_from=self.dn)
                newDn.xCoords = self.dn.xCoords.copy()
                newDn.yCoords = self.dn.yCoords.copy()

                newDn.xCoords[option[0]] = pos[0]
                newDn.yCoords[option[0]] = pos[1]
                if option[0] < self.dn.N:
                    newDn.acceptors[option[0]][0] = pos[0]
                    newDn.acceptors[option[0]][1] = pos[1]
                else:
                    newDn.donors[option[0]-self.dn.N][0] = pos[0]
                    newDn.donors[option[0]-self.dn.N][1] = pos[1]
                newDn.initialize( dopant_placement=False, charge_placement=False)
                yield newDn, option[0], pos



    def doesPositionFit(self, x, y):
        #Legacy helper function
        if x < 0 or x > self.xdim or y < 0 or y > self.ydim:
            return False
        for i in range(len(self.dn.xCoords)):
            if self.float_equals(x, self.dn.xCoords[i]) and self.float_equals(y, self.dn.yCoords[i]):
                return False
        return True

    def float_equals(self, a, b):
        #helper function
        if a < (b+0.001) and a > (b-0.001):
            return True
        else:
            return False


    def randomSearch(self, time_budget):
        #Random search just to see if other searches have some intelligence in them.
        self.setStrategy(len(self.simulation_strategy)-1)
        errors = []
        vals = []
        diffs = []
        best = self.evaluate_error(self.dn)
        bestDn = kmc_dn.kmc_dn(self.dn.N, self.dn.M, self.dn.xdim, self.dn.ydim, 
                self.dn.zdim, electrodes=self.dn.electrodes, copy_from = self.dn)
        real_start_time = time.time()
        time_difference = time.time() - real_start_time
        while time_difference < time_budget:
            print (time_difference)
            self.dn.initialize()
            error = self.evaluate_error(self.dn)
            val = self.validate_error(self.dn)
            vals.append(val)
            diffs.append(math.fabs(error-val))
            if error < best:
                self.copyDnFromBtoA(bestDn, self.dn)
                best = error
            errors.append(error)
            time_difference = time.time() - real_start_time
        return bestDn, errors, vals, diffs

    def saveResults(self, kmc=True, plot=False, prefix="resultDump", index=0):
        #Save search results. Can save both a kmc object but also a traffic visualization.
        if kmc:
            self.best_dn.saveSelf("%s%d.kmc"%(prefix, index))
        if plot:
            self.dn.go_simulation(hops=1000000, record=True)
            plt.clf()
            kmc_utils.visualize_traffic(self.dn, 111, "Result")
            plt.savefig("%s%d.png"%(prefix, index))

    def greedySearch(self):
        #Greedy search.
        best = self.evaluate_error(self.dn)
        print ("Best is %.3f"%(best))
        found = True
        while found:
            found = False
            for neighbour, _, _ in self.yieldNeighbours():
                if best < 0.001:
                    break
                error = self.evaluate_error(neighbour)
                print ("error %.3f"%(error))
                if error < best:
                    found = True
                    print ("New best is %.3f"%(error))
                    best = error
                    self.dn = neighbour
                    break
            if not found and self.x_resolution > self.minimum_resolution:
                if best < self.threshold_error*self.N_tests:
                    self.setStrategy(self.current_strategy+1)
                    best = self.evaluate_error(self.dn)
                    print("New strategy: %d"%(self.current_strategy))
                else:
                    self.x_resolution /= 2
                    self.y_resolution /= 2
                    print("New resolution: %.5f"%(self.x_resolution))
                found = True
        self.best_nd = self.dn


    def appendValidationData(self, error, time_difference, dn=None):
        #Helper function to manage validation information
        if dn is None:
            target = self.dn
        else:
            target = dn
        validation_error = self.validate_error(target)
        self.validations.append((validation_error, error, time_difference))

    def simulatedAnnealingSearch(self, T, annealing_schedule, file_prefix, validation_timestep=3600, animate=True):
        #Simulated annealing search
        real_start_time = time.time()
        annealing_index = 0
        next_validation = validation_timestep
        self.init_search()
        
        T = annealing_schedule[0][0]
        found = True
        best = self.evaluate_error(self.dn)
        abs_best = best
        print ("Best is %.3f"%(best))
        print ("strategy threshold is :%.4f"%(self.threshold_error*self.N_tests))
        found = True
        writer = anim.getWriter(60, "")
        acceptor_plot, donor_plot, history_acceptor_plot, history_donor_plot, text_element, fig = anim.initScatterAnimation(self.dn)
        with writer.saving(fig, "annealingSearch%s.mp4"%(file_prefix), 100):
            anim_counter = 0
            anim_erase_history_at = 480
            while found and annealing_index < len(annealing_schedule):
                found = False
                for neighbour, index, target_pos in self.yieldNeighbours():
                    
                    current_real_time = time.time()
                    time_difference = current_real_time - real_start_time
                    if time_difference > next_validation:
                        self.appendValidationData(best, time_difference)
                        next_validation+=validation_timestep    

                    if time_difference > annealing_schedule[annealing_index][1]:
                        annealing_index+=1
                        if annealing_index < len(annealing_schedule):
                            T = annealing_schedule[annealing_index][0]
                            if annealing_schedule[annealing_index][2] > self.current_strategy:
                                self.setStrategy(annealing_schedule[annealing_index][2])
                                best = self.evaluate_error(self.dn)
                                if best < abs_best:
                                    abs_best = best
                        else:
                            break
                    if T > 0 and annealing_index < len(annealing_schedule)-1:
                        T_from = annealing_schedule[annealing_index][0]
                        T_to = annealing_schedule[annealing_index+1][0]
                        if annealing_index == 0:
                            time_there = (time_difference)/annealing_schedule[annealing_index][1]
                        else:
                            time_there = (time_difference-annealing_schedule[annealing_index-1][1])/annealing_schedule[annealing_index][1]
                        T = T_from + (T_to-T_from)*time_there
                    print ("time difference: %.1f"%(time_difference))
                    if best < 0.001:
                        break
                    error = self.evaluate_error(neighbour)
                    print ("error %.3f, strategy: %d"%(error, self.current_strategy))
                    if self.P(error, best, T):
                        found = True
                        print ("Current best is %.3f"%(error))
                        if animate:
                            refresh = anim_counter >= anim_erase_history_at
                            if refresh:
                                alpha = 0.5
                                anim_counter = 0
                            else:
                                anim_counter+=1
                                alpha = (anim_erase_history_at-anim_counter)/anim_erase_history_at*0.35+0.15
                            anim.animateTransition(self.dn, donor_plot, acceptor_plot, history_donor_plot, history_acceptor_plot, text_element, index, target_pos, writer, 5, refresh, alpha, "Error: %.3f, Time: %.0f sec, strategy: %d"%(best, time_difference, self.current_strategy))
                        best = error
                        
                        self.dn = neighbour
                        if best < self.threshold_error:
                            self.setStrategy(self.current_strategy+1)
                            best = self.evaluate_error(self.dn)
                            print ("New strategy best is %.3f"%(best))
                            print("New strategy: %d"%(self.current_strategy))
                        break
                if not found and self.x_resolution > self.minimum_resolution:
                    print ("Best is %.4f and thershold is %.4f"%(best, self.threshold_error))

                    self.x_resolution /= 2
                    if hasattr(self, "y_resolution"):
                        self.y_resolution /= 2
                    print("New resolution: %.5f"%(self.x_resolution))
                    found = True
        self.appendValidationData(best, time_difference)
        self.best_dn = self.dn
        return best, self.current_strategy, self.validations

    def parallel_simulation(self, dns):
        return #Must be implemented in inheriting class


#Genetic search
    def genetic_search(self, gen_size, time_available, disparity, uniqueness, 
            cross_over_function, mut_pow=1, u_schedule = None, max_generations = 0, 
            mut_rate = 0, initial_dns=None):
        '''
        Genetic search. This implementation has the uniqueness and disparity features.
        Note that the best dn is not returned but saved in self.
        :param gen_size:
            Number of individuals in each generation.
        :param time_available:
            time available in seconds
        :param disparity:
            The higher the disparity the more higher ranking individuals are preferred.
        :param uniqueness:
            The higher the uniqueness value the more different individuals 
                have to be from each other. Mutations are used to force uniquness.
        :param cross_over_function:
            What cross over function is going to be used.
        :param mut_pow:
            Mutation power, the higher this value is, the more likely it is for mutations 
            to change values drastically.
        :param u_schedule:
            Uniqueness schedule. You can define how uniquness value changes throughout generations.
        :param max_generations:
            End the search after processing max_generations-th generation.
        :param mut_rate:
            What is the probability to cause a mutation after cross over.
        :param initial_dns:
            You can provide your own initial dns instead of having them randomly generated.
        :returns:
            A tuple of the evaluation of the best error, the final strategy used and validation scores. In that order.
        '''
        dns = []
        validation_timestep = time_available / 10
        self.current_strategy = 0
        disparity_sum = 0
        preserved_top = 4 - (gen_size % 2)
        cross_over_gen_size = gen_size - preserved_top
        for i in range(cross_over_gen_size):
            disparity_sum+= math.fabs(disparity * ((1-(i+0.5)/cross_over_gen_size)**(disparity-1)))
        disparity_offset = (cross_over_gen_size - disparity_sum) / cross_over_gen_size
        for i in range (gen_size):
            newDn = self.getRandomDn()
            if initial_dns:
                self.copyDnFromBtoA(newDn, initial_dns[i])
            setattr(newDn, "genes", self.getGenes(newDn))
            dns.append(newDn)
        best_dn = dns[0]
        start_time = time.time()
        next_validation = validation_timestep
        self.init_search()
        gen = 0
        if u_schedule is not None:
            us_i = 0
            us_from = uniqueness
        while True:
            gen += 1
            best_error = 1000
            print ("generation: %d"%(gen))
            results = []
            total_error = 0
            i = 0
            if self.parallel > 0:
                self.parallel_simulation(dns)
            for dn in dns:
                error = self.evaluate_error(dn)
                if best_error > error:
                    best_error = error
                    best_dn = dn
                total_error+=error
                results.append((error, dn))
                if i % 1 == 0:
                    print (i)
                i+=1
            time_difference = time.time() - start_time
            if u_schedule is not None:
                if u_schedule[us_i][1] < gen:
                    us_from = u_schedule[us_i][0]
                    us_i += 1
                uniqueness = us_from + (u_schedule[us_i][0]-us_from)\
                    *gen/(u_schedule[us_i][1])
            average_error = total_error / gen_size
            print ("average error: %.3g\nbest error: %.3g"%(average_error, best_error))
            if time_difference > next_validation:
                cur_str = self.current_strategy
                self.setStrategy(len(self.simulation_strategy)-1)
                tmp_error = self.evaluate_error(best_dn)
                self.appendValidationData(tmp_error, time_difference, best_dn)
                self.setStrategy(cur_str)
                next_validation+=validation_timestep
            if time_difference > time_available or (max_generations and gen > max_generations):
                break
            results = sorted(results, key=lambda x:x[0])
            intermediate_dns = []
            new_generation_genes = []
            for i in range(preserved_top):
                new_generation_genes.append(results[i][1].genes) 

            i = 0
            space = 0
            tot = 0
            for _,dn in results:
                space_for_index = math.fabs(disparity * ((1-(i+0.5)/cross_over_gen_size)**(disparity-1))) + disparity_offset
                i+=1
                space += space_for_index
                tot+=space_for_index
                while space >= 1:
                    intermediate_dns.append(dn)
                    space-=1
                if random.random() < space:
                    space-=1
                    intermediate_dns.append(dn)
                if i >= cross_over_gen_size:
                    break
            random.shuffle(intermediate_dns)
            new_generation_genes.extend(self.getNextGenerationGenes(intermediate_dns, uniqueness, cross_over_function, mut_pow, mut_rate))
            tmp_sum = sum([new_generation_genes[y][x] for x in range(len(new_generation_genes[0])) for y in range(len(new_generation_genes))])
            i = 0
            for gene in new_generation_genes:
                self.getDnFromGenes(gene, dns[i])
                i+=1
            tmp_sum2 = sum([new_generation_genes[y][x] for x in range(len(new_generation_genes[0])) for y in range(len(new_generation_genes))])
            assert tmp_sum == tmp_sum2            
            
            if self.current_strategy < len(self.simulation_strategy)-1 \
                    and best_error < self.simulation_strategy[self.current_strategy]['threshold_error']:
                self.setStrategy(self.current_strategy+1)
            elif best_error < self.simulation_strategy[self.current_strategy]['threshold_error']:
                best_dn = dns[0]
                break
        print (best_dn.electrodes)
        print (best_dn.true_voltage)
        print ("\n")
        cur_str = self.current_strategy
        self.setStrategy(len(self.simulation_strategy)-1)
        tmp_error = self.evaluate_error(best_dn)
        self.appendValidationData(tmp_error, time_difference, best_dn)
        self.setStrategy(cur_str)
        self.best_dn = best_dn
        return best_error, self.current_strategy, self.validations



    def getRandomDn(self):
        #Return random dn. Used in initialization of searches.
        newDn = kmc_dn.kmc_dn(self.dn.N, self.dn.M, self.dn.xdim, self.dn.ydim, 
                self.dn.zdim, electrodes=self.dn.electrodes, copy_from = self.dn)
        return newDn


    def getGenes(self, dn):
        # Gen gene encoding of a dopant network object. 
        # Default implementation encodes positions.
        # Gene encoding is a list of uint16 numbers.
        genes = []
        for acceptor in dn.acceptors:
            x = np.uint16(acceptor[0]/dn.xdim * 65535)
            y = np.uint16(acceptor[1]/dn.ydim * 65535)
            genes.append(x)
            genes.append(y)
        for donor in dn.donors:
            x = np.uint16(donor[0]/dn.xdim * 65535)
            y = np.uint16(donor[1]/dn.ydim * 65535)
            genes.append(x)
            genes.append(y)
        return genes
    

    def getNextGenerationGenes(self, dns, uniqueness, cross_over_function, mut_power=1, mut_rate=0):
        '''
        Used by genetic search to generate the genes of the next generation
        :param dns:
            Disparity, elitism and ranking have already been taken into account 
            when generating this list. This list may include multiple references 
            to the same individual.
        :param uniqueness:
            uniqueness value. The distance of all genes have to be higher or equal 
            to any other genes than this value.
        :param cross_over_function:
            Cross over function to be used to perform corssover.
        :param mut_power:
            Mutation power, the higher this value is, the more likely it is for 
            mutations to change values drastically.
        :param mut_rate:
            What is the probability to cause a mutation after cross over.
        :returns:
            List of genes to be used by 
        '''
        newGeneration = []
        for i in range(len(dns)):
            if i % 2 == 0:
                j = i+1
            else:
                j = i-1 
            if j >= len(dns):
                break
            parent_1 = dns[i].genes
            parent_2 = dns[j].genes
            newGenes = cross_over_function(parent_1, parent_2)
            if mut_rate > 0:
                if random.random() < mut_rate:
                    gene = math.floor(random.random()*len(newGenes))
                    newGenes[gene] = dn_search.mutate(newGenes[gene], mut_power)
            ok, problem = self.isAllowed(newGeneration, newGenes, uniqueness, self.genetic_allowed_overlap)
            tries = 0
            while not ok:
                if problem == -1:
                    problem = math.floor(random.random()*len(newGenes))

                newGenes[problem] = dn_search.mutate(newGenes[problem], mut_power)
                ok, problem = self.isAllowed(newGeneration, newGenes, uniqueness, 65)
                tries+=1
                if tries == 100:
                    print ("i: %d, j: %d"%(i, j))
                    print ("that does not bode well")
            newGeneration.append(newGenes)
        return newGeneration


    @staticmethod
    def mutate(a, mut_power):
        # Given initial uint16 a, and mutatuion power, returns a new 
        # uint16 b, with a random bit switched - mutated.
        rnd = math.floor(random.random()**(1/mut_power)*16)
        b = np.uint16(2**rnd)
        return np.bitwise_xor(a, b)


    def isAllowed(self, prev_genes, gene, uniqueness, resolution):
        # Is a gene allowed based on previous genes. 
        # Takes into account uniqueness and resolution.
        for coord in range(0, len(gene), 2):
            for coord2 in range(0, len(gene), 2):
                if coord == coord2:
                    continue
                if dn_search.uInt16Diff( gene[coord], gene[coord2]) < resolution \
                    and dn_search.uInt16Diff(gene[coord+1], gene[coord2+1]) < resolution:
                    return False, coord
        for prev_gene in prev_genes:
            total_diff = 0
            for coord in range(len(gene)):
                total_diff+=dn_search.uInt16Diff(prev_gene[coord], gene[coord])
            if total_diff < uniqueness:
                return False, -1
        return True, -1


    @staticmethod
    def uInt16Diff(a, b):
        if a < b:
            return b-a
        else:
            return a-b


    def singlePointCrossover(self, parent_1_genes, parent_2_genes):
        genes = []
        rnd_index = round(random.random()*len(parent_1_genes))
        genes.extend(parent_1_genes[:rnd_index])
        genes.extend(parent_2_genes[rnd_index:])
        return genes


    def alteredTwoPointCrossOver(self, parent_1_genes, parent_2_genes):
        genes = []
        rnd_index = round(random.random()*self.dn.N*2)
        rnd_index_2 = round(random.random()*self.dn.M*2)+self.dn.N*2
        assert rnd_index <= rnd_index_2, "first index after second"
        assert rnd_index_2 <= len(parent_1_genes), "index longr than gene length"
        genes.extend(parent_1_genes[:rnd_index])
        genes.extend(parent_2_genes[rnd_index:rnd_index_2])
        genes.extend(parent_1_genes[rnd_index_2:])
        assert len(genes) == len(parent_1_genes) == len(parent_2_genes), "gene lengths unstable"
        return genes


    def getDnFromGenes(self, genes, dn):
        # Given genes, a list of uint16 and dopant network object dn,
        # Updates dn to correspond to the gene encoding in genes.
        setattr(dn, "genes", genes)

        for i in range(self.dn.N):
            x = genes[i*2]/65535*self.dn.xdim
            y = genes[i*2+1]/65535*self.dn.ydim
            dn.acceptors[i] = (x, y, 0)
        for i in range(self.dn.M):
            x = genes[self.dn.N*2+i*2]/65535*self.dn.xdim
            y = genes[self.dn.N*2+i*2+1]/65535*self.dn.ydim
            dn.donors[i] = (x, y, 0)
        dn.initialize( dopant_placement=False, charge_placement=False)
    

    @staticmethod
    def nDimSquareDistance(a, b):
        sum=0
        for i in range(len(a)):
            sum+=(a[i]-b[i])**2
        return sum


    @staticmethod
    def getDegree(x, y):
        d = math.sqrt(x**2 + y**2)
        asinv = math.asin(y/d)*180/math.pi
        if x < 0:
            asinv = 180 - asinv
        if asinv < 0:
            asinv+=360
        return asinv


    @staticmethod
    def degreeDistance(a, b):
        x = a[0] - b[0]
        y = a[1] - b[1]
        return dn_search.getDegree(x, y)

    def orderPlacement(self, dn, center):
        distances = []
        for i in range(self.dn.N):
            dist = self.order_distance_function(dn.acceptors[i], center)
            distances.append((dist, i))
        distances = sorted(distances, key=lambda x:x[0])
        newAcceptors = []
        for _,index in distances:
            newAcceptors.append(dn.acceptors[index])
        dn.acceptors = np.array(newAcceptors)
        distances = []
        for i in range(self.dn.M):
            dist = dn_search.nDimSquareDistance(dn.donors[i], center)
            distances.append((dist, i))
        distances = sorted(distances, key=lambda x:x[0])
        newDonors = []
        for _,index in distances:
            newDonors.append(dn.donors[i])
        dn.donors = np.array(newDonors)

    
    def copyDnFromBtoA(self, dna, dnb):
        # Assuming that dna and dnb are based on the same setup and are only different 
        # related to the search at hand, copies the search related values from dnb to dna.
        setattr(dna, "genes", getattr(dnb, "genes", []).copy())
        dna.acceptors = dnb.acceptors.copy()
        dna.donors = dnb.donors.copy()
        dna.initialize( dopant_placement=False, charge_placement=False)
    
    def P(self, e, e0, T):
        # Probabilty function used in simulated annealing.
        if e < e0:
            return True
        elif T < 0.001:
            return False
        else:
            if random.random() < math.exp(-(e-e0)/T):
                return True
            else:
                return False

# Genetic algorithm
# 1. Evaluating a generation is trivial, we already have everything
# 2. Selecting individuals to reproduce: We used idea from literature, Tutorial
# 3. Generating new generation, we have several methods. AGain use Tutorial and Unique measurement.
#  - New random sample
#  - Getting a random neighbour of an existing individual
#  - Combining 2 samples using uniform crossover.
#  - Combining 2 samples using single-point crossover.
# 4. Each method could have some weight, which is gradually changed based on 
#    how much success they provide. Idea to test in the future. First write base-line solution, that can be tested against.
