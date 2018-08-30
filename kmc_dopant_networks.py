'''
Class definition file for the kinetic monte carlo simulations on the
dopant network system. This class incorporates the following algorithm.

Pseudo-code (algorithm):
    # Initialization
    1. Donor placement (N acceptors and M < N donors)
    2. Place charges (N-M)
    3. Solve electrostatic potential from gates (relaxation method?)
    4. Solve compensation energy terms
    # Loop
    5. Calculate Coulomb energy terms
    6. Calculate hopping rates
    7. Hopping event
    8. Current converged?
        No: return to 5.
        Yes: simulation done.

(Average) quantities that are tracked:
    Current through electrodes
    ?Current through domain?
    Number of particles in the system
    Average energy of the system
    
Quantities that can be calculated:
    Mobility?
    Conductance?
    
    

@author: Bram de Wilde (b.dewilde-1@student.utwente.nl)
'''
#TODO calculate a distance matrix outside sim loop
import numpy as np
import matplotlib.pyplot as plt

plt.ioff()

class kmc_dn():
    '''This class is a wrapper for all functions and variables needed to perform
    a kinetic monte carlo simulation of a variable range hopping system'''

    def __init__(self, N, M, xdim, ydim, zdim,
                 electrodes, res = 'unspecified'):
        '''Upon initialization of this class, the impurities and charges are placed.
        They are placed inside a rectangle of xdim by ydim. There are N acceptors
        and M donors.

        ---Input arguments---
        N; number of acceptors
        M; number of donors
        xdim; x dimension size of domain
        ydim; y dimension size of domain
        zdim; z dimension size of domain
        electrodes; electrode configuration, an Px5 np.array, where
            P is the number of electrodes, the first three columns correspond
            to the x, y and coordinates of the electrode, respectively,
            the fourth column holds the electrode voltage and the last column
            tracks the amount of carriers sourced/sinked in the electrode.
        res; resolution used for potential landscape calculation

        ---Class attributes---

        '''

        # Constants
        self.e = 1  #  1.602E-19 Coulomb
        self.eps = 1  # Relative permittivity (11.68 for boron doped Si)
        self.nu = 1
        self.k = 1
        self.T = 1
        self.ab = 100  # Bohr radius (or localization radius)
        self.U = 100  # 5/8 * 1/self.ab   # J
        self.time = 0  # s

        # Initialize variables
        self.N = N
        self.M = M
        self.xdim = xdim
        self.ydim = ydim
        self.zdim = zdim
        self.transitions = np.zeros((N + electrodes.shape[0],
                                     N + electrodes.shape[0]))

        # Check dimensionality
        if(self.ydim == 0 and self.zdim == 0):
            self.dim = 1
        elif(self.zdim == 0):
            self.dim = 2
        else:
            self.dim = 3

        # Fix voltage grid resolution
        if(res == 'unspecified'):
            if(self.dim == 1):
                self.res = self.xdim/100
            if(self.dim == 2):
                self.res =  min([self.xdim, self.ydim])/100
            if(self.dim == 3):
                self.res = min([self.xdim, self.ydim, self.zdim])/100
        else:
            self.res = res

        # Place acceptors and donors
        self.place_dopants_charges()

        # Place electrodes
        self.electrodes = electrodes.copy()

        # Calculate electrostatic potential profile
        self.electrostatic_landscape()

        # Calculate constant energy terms (potential and compensation)
        self.constant_energy()

    def place_dopants_charges(self):
        '''
        Place dopants and charges on a 3D hyperrectangular domain (xdim, ydim, zdim).
        Place N acceptors and M donors. Place N-M charges.
        Returns acceptors (Nx4 array) and donors (Mx3 array). The first three columns
        of each represent the x, y and z coordinates, respectively, of the acceptors
        and donors. The fourth column of acceptors denotes charge occupancy, with
        0 being an unoccupied acceptor and 1 being an occupied acceptor
        '''
        # Initialization
        self.acceptors = np.random.rand(self.N, 4)
        self.donors = np.random.rand(self.M, 3)

        # Place dopants
        self.acceptors[:, 0] *= self.xdim
        self.acceptors[:, 1] *= self.ydim
        self.acceptors[:, 2] *= self.zdim
        self.donors[:, 0] *= self.xdim
        self.donors[:, 1] *= self.ydim
        self.donors[:, 2] *= self.zdim

        # Place charges
        self.acceptors[:, 3] = 0  # Set occupancy to 0
        charges_placed = 0
        while(charges_placed < self.N-self.M):
            trial = np.random.randint(self.N)  # Try a random acceptor
            if(self.acceptors[trial, 3] < 2):
                self.acceptors[trial, 3] += 1  # Place charge
                charges_placed += 1


    def electrostatic_landscape(self):
        '''Numerically solve Laplace with relaxation method'''

        # Grid initialization (for now initialized in 3D for method compatibility)
        self.V = np.zeros((int(self.xdim/self.res) + 2,
                           int(self.ydim/self.res) + 2,
                           int(self.zdim/self.res) + 2))  # +2 for boundaries

        # Convert electrode coordinates to grid coordinates
        self.electrodes_grid = self.electrodes.astype(int)
        for i in range(self.electrodes.shape[0]):
            if(self.dim == 1):
                x = self.electrodes[i, 0]/self.xdim * (self.V.shape[0] - 1)
                self.electrodes_grid[i, :3] = [round(x), 0, 0]
            if(self.dim == 2):
                x = self.electrodes[i, 0]/self.xdim * (self.V.shape[0] - 1)
                y = self.electrodes[i, 1]/self.ydim * (self.V.shape[1] - 1)
                self.electrodes_grid[i, :3] = [round(x), round(y), 0]

            if(self.dim == 3):
                x = self.electrodes[i, 0]/self.xdim * (self.V.shape[0] - 1)
                y = self.electrodes[i, 1]/self.ydim * (self.V.shape[1] - 1)
                z = self.electrodes[i, 2]/self.zdim * (self.V.shape[2] - 1)
                self.electrodes_grid[i, :3] = [round(x),
                                               round(y),
                                               round(z)]

        if(self.dim == 1):
            # Boundary conditions (i.e. electrodes)
            for i in range(self.electrodes.shape[0]):
                self.V[tuple(self.electrodes_grid[i, :3])] = self.electrodes[i, 3]

            # 1D relaxation
            self.V[:, 0, 0] = self.relaxation(self.V[:, 0, 0],
                                              fixedpoints = self.electrodes_grid[:, 0])

        if(self.dim == 2):
            # Boundary conditions (i.e. electrodes)
            for i in range(self.electrodes.shape[0]):
                self.V[tuple(self.electrodes_grid[i, :3])] = self.electrodes[i, 3]

            # 1D boundary relaxation
            points = [val == 0 for val in self.electrodes_grid[:, 1]]  # Find electrodes that lie on border [:, 0, 0]
            self.V[:, 0, 0] = self.relaxation(self.V[:, 0, 0],
                                              fixedpoints = self.electrodes_grid[points, 0])
            points = [val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]]
            self.V[:, -1, 0] = self.relaxation(self.V[:, -1, 0],
                                              fixedpoints = self.electrodes_grid[points, 0])
            points = [val == 0 for val in self.electrodes_grid[:, 0]]
            self.V[0, :, 0] = self.relaxation(self.V[0, :, 0],
                                              fixedpoints = self.electrodes_grid[points, 1])
            points = [val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]]
            self.V[-1, :, 0] = self.relaxation(self.V[-1, :, 0],
                                              fixedpoints = self.electrodes_grid[points, 1])

            # 2D relaxation
            self.V[:, :, 0] = self.relaxation(self.V[:, :, 0],
                                              fixedpoints = self.electrodes_grid[:, :2])

        if(self.dim == 3):
            # Boundary conditions (i.e. electrodes)
            for i in range(self.electrodes.shape[0]):
                self.V[tuple(self.electrodes_grid[i, :3])] = self.electrodes[i, 3]

            # 1D boundary relaxation
            # x-y plane (z=0)
            # Border [:, 0, 0]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 1]])
                   &  np.asarray([val == 0 for val in self.electrodes_grid[:, 2]]))
            self.V[:, 0, 0] = self.relaxation(self.V[:, 0, 0],
                                              fixedpoints = self.electrodes_grid[points, 0])
            # Border [:, -1, 0]
            points = (np.asarray([val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]])
                &     np.asarray([val == 0 for val in self.electrodes_grid[:, 2]]))
            self.V[:, -1, 0] = self.relaxation(self.V[:, -1, 0],
                                              fixedpoints = self.electrodes_grid[points, 0])
            # Border [0, :, 0]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == 0 for val in self.electrodes_grid[:, 2]]))
            self.V[0, :, 0] = self.relaxation(self.V[0, :, 0],
                                              fixedpoints = self.electrodes_grid[points, 1])

            # Border [-1, :, 0]
            points = (np.asarray([val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == 0 for val in self.electrodes_grid[:, 2]]))
            self.V[-1, :, 0] = self.relaxation(self.V[-1, :, 0],
                                              fixedpoints = self.electrodes_grid[points, 1])

            # x-y plane (z=-1)
            # Border [:, 0, -1]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 1]])
                &     np.asarray([val == self.V.shape[2]-1 for val in self.electrodes_grid[:, 2]]))
            self.V[:, 0, -1] = self.relaxation(self.V[:, 0, -1],
                                              fixedpoints = self.electrodes_grid[points, 0])
            # Border [:, -1, -1]
            points = (np.asarray([val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]])
                &     np.asarray([val == self.V.shape[2]-1 for val in self.electrodes_grid[:, 2]]))
            self.V[:, -1, -1] = self.relaxation(self.V[:, -1, -1],
                                              fixedpoints = self.electrodes_grid[points, 0])
            # Border [0, :, -1]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 0]] )
                &     np.asarray([val == self.V.shape[2]-1 for val in self.electrodes_grid[:, 2]]))
            self.V[0, :, -1] = self.relaxation(self.V[0, :, -1],
                                              fixedpoints = self.electrodes_grid[points, 1])
            # Border [-1, :, -1]
            points = (np.asarray([val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == self.V.shape[2]-1 for val in self.electrodes_grid[:, 2]]))
            self.V[-1, :, -1] = self.relaxation(self.V[-1, :, -1],
                                              fixedpoints = self.electrodes_grid[points, 1])

            # Remaining four borders (z != 0 or -1)
            # Border [0, 0, :]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == 0 for val in self.electrodes_grid[:, 1]]))
            self.V[0, 0, :] = self.relaxation(self.V[0, 0, :],
                                              fixedpoints = self.electrodes_grid[points, 2])
            # Border [0, -1, :]
            points = (np.asarray([val == 0 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]]))
            self.V[0, -1, :] = self.relaxation(self.V[0, -1, :],
                                              fixedpoints = self.electrodes_grid[points, 2])
            # Border [-1, 0, :]
            points = (np.asarray([val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == 0 for val in self.electrodes_grid[:, 1]]))
            self.V[-1, 0, :] = self.relaxation(self.V[-1, 0, :],
                                              fixedpoints = self.electrodes_grid[points, 2])
            # Border [-1, -1, :]
            points = (np.asarray([val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]])
                &     np.asarray([val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]]))
            self.V[-1, -1, :] = self.relaxation(self.V[-1, -1, :],
                                              fixedpoints = self.electrodes_grid[points, 2])

            #2D boundary relaxation
            # Plane [:, :, 0]
            points = [val == 0 for val in self.electrodes_grid[:, 2]]
            self.V[:, :, 0] = self.relaxation(self.V[:, :, 0],
                                              fixedpoints = self.electrodes_grid[points, :2])
            # Plane [:, :, -1]
            points = [val == self.V.shape[2]-1 for val in self.electrodes_grid[:, 2]]
            self.V[:, :, -1] = self.relaxation(self.V[:, :, -1],
                                              fixedpoints = self.electrodes_grid[points, :2])
            # Plane [0, :, :]
            points = [val == 0 for val in self.electrodes_grid[:, 0]]
            self.V[0, :, :] = self.relaxation(self.V[0, :, :],
                                              fixedpoints = self.electrodes_grid[points, 1:3])
            # Plane [-1, :, :]
            points = [val == self.V.shape[0]-1 for val in self.electrodes_grid[:, 0]]
            self.V[-1, :, :] = self.relaxation(self.V[-1, :, :],
                                              fixedpoints = self.electrodes_grid[points, 1:3])
            # Plane [:, 0, :]
            points = [val == 0 for val in self.electrodes_grid[:, 1]]
            fixedpoints = np.delete(self.electrodes_grid[points, :3], 1, 1)
            self.V[:, 0, :] = self.relaxation(self.V[:, 0, :], fixedpoints = fixedpoints)
            # Plane [:, -1, :]
            points = [val == self.V.shape[1]-1 for val in self.electrodes_grid[:, 1]]
            fixedpoints = np.delete(self.electrodes_grid[points, :3], 1, 1)
            self.V[:, -1, :] = self.relaxation(self.V[:, -1, :], fixedpoints = fixedpoints)

            #3D relaxation
            self.V = self.relaxation(self.V, fixedpoints = self.electrodes_grid[:, :3])

    def constant_energy(self):
        '''Solve the constant energy terms for each acceptor site. These
        are terms due to the electrostatic landscape and the donor atoms.'''
        # Initialization
        self.E_constant = np.zeros((self.N, 1))

        for i in range(self.acceptors.shape[0]):
            # Add electrostatic potential
            if(self.dim == 1):
                x = self.acceptors[i, 0]/self.xdim * (self.V.shape[0] - 3) + 1
                self.E_constant[i] += self.e*self.V[int(round(x)), 0, 0]

            if(self.dim == 2):
                x = self.acceptors[i, 0]/self.xdim * (self.V.shape[0] - 3) + 1
                y = self.acceptors[i, 1]/self.ydim * (self.V.shape[1] - 3) + 1
                self.E_constant[i] += self.e*self.V[int(round(x)),
                                                    int(round(y)), 0]

            if(self.dim == 3):
                x = self.acceptors[i, 0]/self.xdim * (self.V.shape[0] - 3) + 1
                y = self.acceptors[i, 1]/self.ydim * (self.V.shape[1] - 3) + 1
                z = self.acceptors[i, 2]/self.zdim * (self.V.shape[2] - 3) + 1
                self.E_constant[i] += self.e*self.V[int(round(x)),
                                                    int(round(y)),
                                                    int(round(z))]

            # Add compensation
            self.E_constant[i] += -self.e**2/(4 * np.pi * self.eps) * sum(
                    1/self.dist(self.acceptors[i, :3], self.donors[k, :3]) for k in range(self.donors.shape[0]))


    def update_transition_matrix(self):
        '''Updates the transition matrix based on the current occupancy of
        acceptors'''
        # Loop over possible hops from site i -> site j
        for i in range(self.transitions.shape[0]):
            for j in range(self.transitions.shape[0]):
                if(not self.transition_possible(i, j)):
                    self.transitions[i, j] = 0
                else:
                    eij = self.energy_difference(i, j)
                    self.transitions[i, j] = self.rate(i, j, eij)

    def pick_event(self):
        '''Based in the transition matrix self.transitions, pick a hopping event'''
        # Initialization
        self.P = np.zeros((self.transitions.shape[0]**2))  # Probability list

        # Calculate cumulative transition rate (partial sums)
        for i in range(self.transitions.shape[0]):
            for j in range(self.transitions.shape[0]):
                if(i == 0 and j == 0):
                    self.P[i*self.transitions.shape[0] + j] = self.transitions[i, j]
                else:
                    self.P[i*self.transitions.shape[0] + j] = self.P[i*self.transitions.shape[0] + j - 1] + self.transitions[i, j]

        # Normalization
        self.P = self.P/self.P[-1]

        # Randomly determine event
        event = np.random.rand()

        # Find transition index
        event = min(np.where(self.P >= event)[0])

        # Convert to acceptor/electrode indices
        self.transition = [int(np.floor(event/self.transitions.shape[0])),
                           int(event%self.transitions.shape[0])]

        # Perform hop
        if(self.transition[0] < self.N):  # Hop from acceptor
            self.acceptors[self.transition[0], 3] -= 1
        else:  # Hop from electrode
            self.electrodes[self.transition[0] - self.N, 4] -= 1
        if(self.transition[1] < self.N):  # Hop to acceptor
            self.acceptors[self.transition[1], 3] += 1
        else:  # Hop to electrode
            self.electrodes[self.transition[1] - self.N, 4] += 1

        # Increment time
        self.time += 1/self.transitions[self.transition[0], self.transition[1]]


    def simulate(self, interval = 500, tol = 1E-3):
        '''Performs a kmc simulation and checks current convergence after [interval]
        hop events.'''
        # Initialization
        self.old_current = np.ones((self.electrodes.shape[0]))
        self.current = np.zeros((self.electrodes.shape[0]))
        self.time = 0  # Reset simulation time
        for i in range(self.electrodes.shape[0]):
            self.electrodes[i, 4] = 0  # Reset current


        # Simulation loop
        converged = False
        self.old_current *= np.inf
        while(not converged):
            for i in range(interval):
                # Hopping event
                self.update_transition_matrix()
                self.pick_event()

            # Calculate currents
            self.current = self.electrodes[:, 4]/self.time

            # Check convergence
            if(np.linalg.norm(self.old_current - self.current, 2)/np.linalg.norm(self.current,2) < tol):
                converged = True
            else:
                self.old_current = self.current.copy()  # Store current
            print(self.current)

        #TODO Some progress statement print
    
    def simulate_discrete(self, hops):
        '''Perform a kmc simulation, but with a predetermined amount of hops'''
        # Initialization
        self.time = 0  # Reset simulation time
        for i in range(self.electrodes.shape[0]):
            self.electrodes[i, 4] = 0  # Reset current
            
        # Simulation loop
        for i in range(hops):
            # Hopping event
            self.update_transition_matrix()
            self.pick_event()
            
        return 'Done!'
    
    def transition_possible(self, i, j):
        '''Check if a hop from i -> j is possible. Returns True if transition is
        allowed, otherwise returns False'''
        possible = True
        if(i >= self.N and j >= self.N):
            possible = False  # No transition electrode -> electrode
        elif(i >= self.N and j < self.N):
            if(self.acceptors[j, 3] == 1):
                possible = False  # No transition electrode -> occupied
        elif(i < self.N and j >= self.N):
            if(self.acceptors[i, 3] == 0):
                possible = False  # No transition empty -> electrode
        elif(i == j):
            possible = False  # No transition to same acceptor
        elif(i < self.N and j < self.N):
            if(self.acceptors[i, 3] == 0
               or self.acceptors[j, 3] == 1):
                possible = False  # No transition empty -> or -> occupied
        return possible

    def energy_difference(self, i, j):
        '''Calculate the energy difference if a hop were to occur from site i -> j.
        This particular way of calculating the energy difference is documented
        in the thesis of Jeroen v. Gelder.'''

        # Calculate ei
        if(i >= self.N):
            ei = 0  # Hop from electrode into system
        else:
            # Acceptor interaction loop
            acc_int = 0
            for k in range(self.acceptors.shape[0]):
                if(k != i):
                    acc_int += ((1 - self.acceptors[k, 3])
                                /self.dist(self.acceptors[i, :3],
                                           self.acceptors[k, :3]))
            ei = (self.e**2/(4 * np.pi * self.eps) * acc_int
                + self.E_constant[i])
            if(self.acceptors[i, 3] == 2):
                ei += self.U

        # Calculate ej
        if(j >= self.N):
            ej = 0  # Hop to electrode
        else:
            # Acceptor interaction loop
            acc_int = 0
            for k in range(self.acceptors.shape[0]):
                if(k != j):
                    acc_int += ((1 - self.acceptors[k, 3])
                            /self.dist(self.acceptors[j, :3],
                                       self.acceptors[k, :3]))
            ej = (self.e**2/(4 * np.pi * self.eps) * acc_int
                + self.E_constant[j])
            if(self.acceptors[j, 3] == 1):
                ej += self.U

        # Calculate energy difference
        if(i >= self.N or j >= self.N):
            eij = ej - ei  # No Coulomb interaction for electrode hops
        else:
            eij = ej - ei + (self.e**2/(4 * np.pi * self.eps)
                        /self.dist(self.acceptors[i, :3],
                                   self.acceptors[j, :3]))
        return eij

    def rate(self, i, j, eij):
        '''Calculate the transition rate for hop i->j based on the energy difference
        eij. The hopping rate used here is the Miller-Abrahams rate.'''
        # Calculate hopping distance
        if(i >= self.N):  # Hop from electrode
            hop_dist = self.dist(self.electrodes[i-self.N, :3],
                                 self.acceptors[j, :3])
        elif(j >= self.N):  # Hop to electrode
            hop_dist = self.dist(self.acceptors[i, :3],
                                 self.electrodes[j-self.N, :3])
        else:  # Hop acceptor -> acceptor
            hop_dist = self.dist(self.acceptors[i, :3],
                                 self.acceptors[j, :3])

        # Calculate transition rate
        if(eij < 0):
            transition_rate = self.nu*np.exp(-2*hop_dist/self.ab
                                                    - eij/(self.k*self.T))
        else:
            transition_rate = self.nu*np.exp(-2*hop_dist/self.ab)

        return transition_rate
    
    def visualize(self):
        '''Returns a figure which shows the domain with potential profile. It 
        also show all dopants with acceptor occupancy.'''
        if(self.dim == 2):
            # Initialize figure
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.set_xlim(right=self.xdim)
            ax.set_ylim(top=self.ydim)
            
            ## Plot potential profile
            ax.imshow(self.V[:, :, 0].transpose(), interpolation='bicubic',
                      origin='lower', extent=(0, self.xdim, 0, self.ydim))
            
            
            # Plot impurity configuration (red = 2, orange = 1, black = 0 holes)
            colors = ['red' if i==2
                      else 'orange' if i==1
                      else 'black' for i in self.acceptors[:, 3]]
            ax.scatter(self.acceptors[:, 0], self.acceptors[:, 1], c = colors, marker='o')
            
            ax.scatter(self.donors[:, 0], self.donors[:, 1], marker='x')
            
        return fig


    @staticmethod
    def dist(ri, rj):
        '''Calculate cartesian distance between 3D vectors ri and rj'''
        return np.sqrt((ri[0] - rj[0])**2 + (ri[1] - rj[1])**2 + (ri[2] - rj[2])**2)

    @staticmethod
    def relaxation(A, alpha=1, tol=1E-3, fixedpoints = np.asarray([])):
        '''Perform relaxation method on 1, 2 or 3D vector A. alpha is the
        relaxation parameter and tol the tolerance for convergence.
        fixedpoints is an N x dim np.ndarray with coordinates that will never be
        updated.'''
        # Check if fixedpoints is a numpy array
        if(type(fixedpoints) != np.ndarray):
            print('fixedpoints must be a numpy array!')
            return
        dim = len(A.shape)
        B = A.copy()  # Otherwise method changes object A

        if(dim == 1):
            # Initialization
            B_old = B + 1

            # Relaxation loop
            while((np.linalg.norm(B - B_old)
                    /np.linalg.norm(B)) > tol):
                B_old = B.copy()  # Store previous V

                # Loop over internal elements
                for i in range(1, A.shape[0]-1):
                    B[i] = alpha * 1/2 * (B_old[i-1] + B_old[i+1])

                # Loop over fixed points
                for i in range(fixedpoints.shape[0]):
                    B[int(fixedpoints[i])] = B_old[int(fixedpoints[i])]

        if(dim == 2):
            # Initialization
            B_old = B + 1

            # Relaxation loop
            while((np.linalg.norm(B - B_old)
                    /np.linalg.norm(B)) > tol):
                B_old = B.copy()  # Store previous V

                # Loop over internal elements
                for i in range(1, A.shape[0]-1):
                    for j in range(1, A.shape[1]-1):
                        B[i, j] = alpha * 1/4 * (B_old[i-1, j] + B_old[i+1, j]
                                                 + B_old[i, j-1] + B_old[i, j+1])

                # Loop over fixed points
                for i in range(fixedpoints.shape[0]):
                    B[tuple(fixedpoints[i])] = B_old[tuple(fixedpoints[i])]

        if(dim == 3):
            # Initialization
            B_old = B + 1

            # Relaxation loop
            while((np.linalg.norm(B - B_old)
                    /np.linalg.norm(B)) > tol):
                B_old = B.copy()  # Store previous V

                # Loop over internal elements
                for i in range(1, A.shape[0]-1):
                    for j in range(1, A.shape[1]-1):
                        for k in range(1, A.shape[2]-1):
                            B[i, j, k] = alpha * 1/6 * (B_old[i-1, j, k]
                                                        + B_old[i+1, j, k]
                                                        + B_old[i, j-1, k]
                                                        + B_old[i, j+1, k]
                                                        + B_old[i, j, k-1]
                                                        + B_old[i, j, k+1])

                # Loop over fixed points
                for i in range(fixedpoints.shape[0]):
                    B[tuple(fixedpoints[i])] = B_old[tuple(fixedpoints[i])]

        return B
