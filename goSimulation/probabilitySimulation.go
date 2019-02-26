package main

import "fmt"
import "math"
import "math/rand"


func calcProbTransitions(transitions [][]float64, distances [][]float64, occupation []float64, 
    site_energies []float64, R float64, I_0 float64, kT float64, nu float64, NSites int, 
    N int, transitions_constant [][]float64, difference []float64) float64 {
	tot_rates := 0.0
    for i := 0; i < N; i++ {
        for j := 0; j < N; j++ {
            base_prob := probTransitionPossible(i, j, NSites, occupation)
			var dE float64
			if i < NSites && j < NSites {
				dE = site_energies[j] - site_energies[i] - I_0*R/distances[i][j]
			} else {
				dE = site_energies[j] - site_energies[i]
			}
			
			if dE > 0 {
				transitions[i][j] = base_prob * nu * math.Exp(float64(-dE/kT))
			} else {
				transitions[i][j] = base_prob * nu
			}
			transitions[i][j]*=transitions_constant[i][j]
			tot_rates+=transitions[i][j]
			if i < NSites {
				difference[i]-=transitions[i][j]
			}
			if j < NSites {
				difference[j]+=transitions[i][j]
			}
        }
	}
	return tot_rates
}

func probTransitionPossible(i int, j int, NSites int, occupation []float64) float64 {
    if i >= NSites && j >= NSites {
        return 0
    } else if i>= NSites {
        return 1-occupation[j]
    } else if j>= NSites {
        return occupation[i]
    } else {
        return (1-occupation[j])*occupation[i]
    }
}
  

func probSimulate(NSites int, NElectrodes int, nu float64, kT float64, I_0 float64, R float64, time float64,
    	occupation []float64, distances [][]float64, E_constant []float64, transitions_constant [][]float64,
    	electrode_occupation []float64, site_energies []float64, hops int) float64 {
	N := NSites + NElectrodes
	transitions := make([][]float64, N)
	difference := make([]float64, NSites)
	eoDifference := make([]float64, NElectrodes)
	
	//fmt.Println(occupation)

	for i := 0; i < NElectrodes; i++ {
		electrode_occupation[i] = 0.0
	}

	for i := 0; i < N; i++ {
		transitions[i] = make([]float64, N)
		for j := 0; j < N; j++ {
			if transitions_constant[i][j] < 0{
				fmt.Println("Transition constant negative")
			}
		}
	}
    allowed_change := 1.0

	showStep := 4
	for hop := 0; hop < hops; hop++ {
		for i := 0; i < NSites; i++ {
			difference[i] = 0
			acceptor_interaction := float64(0)
			for j := 0; j < NSites; j++ {
				if j != i {
					acceptor_interaction+= (1-occupation[j])/distances[i][j]
				}
			}
			site_energies[i] = E_constant[i] - I_0*R*acceptor_interaction
		}
		for i:= 0; i < NElectrodes; i++ {
			eoDifference[i] = 0
		}

		tot_rates := calcProbTransitions(transitions, distances, occupation, site_energies, R, I_0, kT, nu, NSites, N, transitions_constant, difference)
		var max_rate float64 = math.Max(1.0, 1/tot_rates)
		for i := 0; i < NSites; i++ {
			newVal := occupation[i] + max_rate*difference[i]
			if newVal < 0 {
				max_rate = occupation[i]/-difference[i]/allowed_change
			}
			if newVal > 1 {
				max_rate = (1-occupation[i])/difference[i]/allowed_change
			}
		}
		
		time += rand.ExpFloat64() * (max_rate)



		for i := 0; i < N; i++ {
			for j := 0; j < N; j++ {
				if i >= NSites && j >= NSites {
					break
				}
				rate := transitions[i][j]*max_rate
				if i < NSites {
					if occupation[i] < rate {
						rate = occupation[i]
					}
					occupation[i]-=rate
				} else {
					electrode_occupation[i-NSites]-=rate
					eoDifference[i-NSites]-=transitions[i][j]/tot_rates
				}
				if j < NSites {
					occupation[j]+=rate
				} else {
					electrode_occupation[j-NSites]+=rate
					eoDifference[j-NSites]+=transitions[i][j]/tot_rates
				}
			}
		}
		if hop % showStep == 0 {
			showStep*=8
			allowed_change*=2
			//current := electrode_occupation[0] / time
			//fmt.Printf("Hop: %d, max_rate: %.3f, tot_rates: %.2f, current: %.2f, time: %.2f\n", hop, max_rate, tot_rates, current, time)
			//fmt.Printf("Occupation at hop: %v\n", occupation)
			
			/*ave_time := 0.98 / (tot_rates)
			for i:=0; i < NElectrodes; i++ {
				fmt.Printf("The expected average current for %d is %.3f\n", i, eoDifference[i]/ave_time)
			}*/
		}
	}
	/*fmt.Printf("Occupation: %.4v\n", occupation)
	fmt.Printf("Last difference: %.4v\n", difference)
	fmt.Printf("Site energies: %.4v\n", site_energies)
	fmt.Printf("Constants: %.4v\n", transitions_constant)

	fmt.Println(time)
	fmt.Println(electrode_occupation)
	for i := 0; i < len(electrode_occupation); i++ {
		fmt.Println(electrode_occupation[i]/time)
	}*/
	
	return time
}