"""Module used for the execution of the evolutionary algorithm."""
import time

import numpy as np

from evopy.individual import Individual
from evopy.progress_report import ProgressReport
from evopy.strategy import Strategy
from evopy.utils import random_with_seed


class EvoPy:
    """Main class of the EvoPy package."""

    def __init__(self, fitness_function, individual_length, warm_start=None, generations=100,
                 population_size=30, num_children=1, mean=0, std=1, maximize=False,
                 strategy=Strategy.SINGLE_VARIANCE, random_seed=None, reporter=None,
                 target_fitness_value=None, target_tolerance=1e-5, max_run_time=None,
                 max_evaluations=None, bounds=None, max_age=0, forces_config=None, mutation_rate=1):
        """Initializes an EvoPy instance.

        :param fitness_function: the fitness function on which the individuals are evaluated
        :param individual_length: the length of each individual
        :param warm_start: the individual to start from
        :param generations: the number of generations to execute
        :param population_size: the population size of each generation
        :param num_children: the number of children generated per parent individual
        :param mean: the mean for sampling the random offsets of the initial population
        :param std: the standard deviation for sampling the random offsets of the initial population
        :param maximize: whether the fitness function should be maximized or minimized
        :param strategy: the strategy used to generate offspring by individuals. For more
                         information, check the Strategy enum
        :param random_seed: the seed to use for the random number generator
        :param reporter: callback to be invoked at each generation with a ProgressReport as argument
        :param target_fitness_value: target fitness value for early stopping
        :param target_tolerance: tolerance to within target fitness value is to be acquired
        :param max_run_time: maximum time allowed to run in seconds
        :param max_evaluations: maximum allowed number of fitness function evaluations
        :param bounds: bounds for the sampling the parameters of individuals
        """
        self.fitness_function = fitness_function
        self.individual_length = individual_length
        self.warm_start = warm_start
        self.generations = generations
        self.population_size = population_size
        self.num_children = num_children
        self.mean = mean
        self.std = std
        self.maximize = maximize
        self.strategy = strategy
        self.random_seed = random_seed
        self.random = random_with_seed(self.random_seed)
        self.reporter = reporter
        self.target_fitness_value = target_fitness_value
        self.target_tolerance = target_tolerance
        self.max_run_time = max_run_time
        self.max_evaluations = max_evaluations
        self.bounds = bounds
        self.max_age = max_age
        self.evaluations = 0
        self.forces_config=forces_config
        self.mutation_rate=mutation_rate

    def _check_early_stop(self, start_time, best):
        """Check whether the algorithm can stop early, based on time and fitness target.

        :param start_time: the starting time to compare against
        :param best: the current best individual
        :return: whether the algorithm should be terminated early
        """
        return (self.max_run_time is not None
                and (time.time() - start_time) > self.max_run_time) \
               or \
               (self.target_fitness_value is not None
                and abs(best.fitness - self.target_fitness_value) < self.target_tolerance) \
               or (self.max_evaluations is not None
                and self.evaluations >= self.max_evaluations)

    def run(self):
        """Run the evolutionary strategy algorithm.

        :return: the best genotype found
        """
        if self.individual_length == 0:
            return None

        start_time = time.time()

        population = self._init_population()
        best = sorted(population, reverse=self.maximize,
                      key=lambda individual: individual.evaluate(self.fitness_function))[0]

        for generation in range(self.generations):
            children = [parent.reproduce() for _ in range(self.num_children)
                        for parent in population]
            population = self._age_population(population)
            population = sorted(children+population, reverse=self.maximize,
                                key=lambda individual: individual.evaluate(self.fitness_function))
            self.evaluations += len(population)
            population = population[:self.population_size]
            best = population[0]

            should_stop = self._check_early_stop(start_time, best) or generation == self.generations - 1

            if self.reporter is not None:
                mean = np.mean([x.fitness for x in population])
                std = np.std([x.fitness for x in population])
                self.reporter(ProgressReport(generation, self.evaluations, best, best.genotype, best.fitness, mean, std, time.time() - start_time, should_stop))

            if should_stop:
                break

        return best.genotype

    def _age_population(self, population):
        """
        Increases the age of individuals in the population by 1 and kills individuals that reached the maximum age and
        """
        population = list(filter(lambda i: i.age < self.max_age, population))
        for individual in population:
            individual.age += 1
        return population

    def _init_population(self):
        if self.strategy == Strategy.SINGLE_VARIANCE:
            strategy_parameters = self.random.randn(1)
        elif self.strategy == Strategy.MULTIPLE_VARIANCE:
            strategy_parameters = self.random.randn(self.individual_length)
        elif self.strategy == Strategy.FULL_VARIANCE:
            strategy_parameters = self.random.randn(
                int((self.individual_length + 1) * self.individual_length / 2))
        else:
            raise ValueError("Provided strategy parameter was not an instance of Strategy")

        if self.warm_start is None:
            population_parameters = np.asarray([
                self.random.normal(loc=0, scale=self.std, size=self.individual_length)
                for n in range(self.population_size)
            ])
        else:
            population_parameters = self.warm_start

        # Make sure parameters are within bounds
        if self.bounds is not None:
            population_parameters = np.clip(population_parameters, self.bounds[0], self.bounds[1])
            #oob_indices = (population_parameters < self.bounds[0]) | (population_parameters > self.bounds[1])
            #population_parameters[oob_indices] = self.random.uniform(self.bounds[0], self.bounds[1], size=np.count_nonzero(oob_indices))

        return [
            Individual(
                # Initialize genotype within possible bounds
                parameters,
                # Set strategy parameters
                self.strategy, strategy_parameters,
                # Set seed and bounds for reproduction
                random_seed=self.random,
                bounds=self.bounds,
                forces_config=self.forces_config,
                mutation_rate = self.mutation_rate
            ) for parameters in population_parameters
        ]
