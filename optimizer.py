import concurrent.futures
import math
import os
import random


class HFTAlgorithmOptimizer:
    def __init__(self, backtest_func, param_space, exploration_constant=1.5):
        self.backtest_func = backtest_func
        self.param_space = param_space
        self.c = exploration_constant

        self.n_arms = len(param_space)
        self.counts = [0] * self.n_arms
        self.values = [0.0] * self.n_arms

    def select_arm(self, total_steps):
        untried_arms = [arm for arm, count in enumerate(self.counts) if count == 0]
        if untried_arms:
            return random.choice(untried_arms)

        ucb_values = [0.0] * self.n_arms
        for arm in range(self.n_arms):
            exploitation = self.values[arm]
            exploration = self.c * math.sqrt(math.log(total_steps) / float(self.counts[arm]))
            ucb_values[arm] = exploitation + exploration

        return ucb_values.index(max(ucb_values))

    def update(self, chosen_arm, reward):
        self.counts[chosen_arm] += 1
        n = self.counts[chosen_arm]
        value = self.values[chosen_arm]
        self.values[chosen_arm] = ((n - 1) / float(n)) * value + (1 / float(n)) * reward

    def run_optimization_parallel(self, total_iterations, max_workers=None):
        if max_workers is None:
            max_workers = max(1, os.cpu_count() - 1)

        print(f"Starting parallel optimization with {max_workers} workers.")

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            step = 1
            while step <= total_iterations:
                batch_size = min(max_workers, total_iterations - step + 1)
                selected_arms = []

                for _ in range(batch_size):
                    arm = self.select_arm(step)
                    selected_arms.append(arm)
                    self.counts[arm] += 1
                    step += 1

                for arm in selected_arms:
                    self.counts[arm] -= 1

                params_batch = [self.param_space[arm] for arm in selected_arms]
                rewards = list(executor.map(self.backtest_func, params_batch))

                for arm, reward in zip(selected_arms, rewards):
                    self.update(arm, reward)

                if (step - 1) % (max_workers * 2) == 0 or (step - 1) == total_iterations:
                    best_current_arm = self._best_evaluated_arm()
                    print(
                        f"[Iteration {step - 1}/{total_iterations}] "
                        f"best_score={self.values[best_current_arm]:.4f} | "
                        f"best_params={self.param_space[best_current_arm]}"
                    )

        best_arm = self._best_evaluated_arm()
        return self.param_space[best_arm], self.values[best_arm]

    def _best_evaluated_arm(self):
        evaluated_arms = [arm for arm, count in enumerate(self.counts) if count > 0]
        if not evaluated_arms:
            return 0
        return max(evaluated_arms, key=lambda arm: self.values[arm])
