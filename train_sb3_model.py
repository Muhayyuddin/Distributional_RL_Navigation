# from tabnanny import verbose
import numpy as np
import sys
sys.path.insert(0,"./thirdparty")
from thirdparty import PPO
from thirdparty import A2C
from thirdparty import DQN
from thirdparty import QRDQN
import gym
import os
import argparse
import itertools
from multiprocessing import Pool
import json
from datetime import datetime

parser = argparse.ArgumentParser(description="Train sb3 model")

parser.add_argument(
    "-C",
    "--config-file",
    dest="config_file",
    type=open,
    required=True,
    help="configuration file for experiment parameters",
)
parser.add_argument(
    "-P",
    "--num-procs",
    dest="num_procs",
    type=int,
    default=1,
    help="number of subprocess workers to use for trial parallelization",
)
parser.add_argument(
    "-D",
    "--device",
    dest="device",
    type=str,
    default="auto",
    help="device to run all subprocesses, could only specify 1 device in each run"
)

def product(*args, repeat=1):
    # This function is a modified version of 
    # https://docs.python.org/3/library/itertools.html#itertools.product
    pools = [tuple(pool) for pool in args] * repeat
    result = [[]]
    for pool in pools:
        result = [x+[y] for x in result for y in pool]
    for prod in result:
        yield tuple(prod)

def trial_params(params):
    if isinstance(params,(str,int,float)):
        return [params]
    elif isinstance(params,list):
        return params
    elif isinstance(params, dict):
        keys, vals = zip(*params.items())
        mix_vals = []
        for val in vals:
            val = trial_params(val)
            mix_vals.append(val)
        return [dict(zip(keys, mix_val)) for mix_val in itertools.product(*mix_vals)]
    else:
        raise TypeError("Parameter type is incorrect.")

def params_dashboard(params):
    print("\n====== Experiment Setup ======\n")
    print("seed: ",params["seed"])
    print("total_timesteps: ",params["total_timesteps"])
    print("eval_freq: ",params["eval_freq"])
    print("\n")

def run_trial(device,params):
    
    exp_dir = os.path.join(params["save_dir"],
                           "experiment_"+params["experiment_time"],
                           "seed_"+str(params["seed"]))
    os.makedirs(exp_dir)

    param_file = os.path.join(exp_dir,"trial_config.json")
    with open(param_file, 'w+') as outfile:
        json.dump(params, outfile)
    
    train_env = gym.make('marinenav_env:marinenav_env-v0',seed=params["seed"])
    evaluate_env = gym.make('marinenav_env:marinenav_env-v0',seed=0) 

    #model = DQN(policy='MlpPolicy',
    #            env=train_env,
    #            train_freq=1,
    #            verbose=1,
    #            seed=1,
    #            gamma=train_env.discount,
    #            device=device)
    
    policy_args = {"n_quantiles":8}
    model = QRDQN(policy='MlpPolicy',
                  env=train_env,
                  learning_starts=10000,
                  policy_kwargs=policy_args,
                  train_freq=1,
                  exploration_fraction=0.1,
                  exploration_initial_eps=1.0,
                  exploration_final_eps=0.05,
                  verbose=1,
                  seed=1,
                  gamma=train_env.discount,
                  device=device)

    model.learn(total_timesteps=params["total_timesteps"],
                eval_env=evaluate_env,
                eval_freq=params["eval_freq"],
                n_eval_episodes=1, 
                eval_log_path=exp_dir)
    
    train_env.close()
    evaluate_env.close()

if __name__ == "__main__":
    args = parser.parse_args()
    params = json.load(args.config_file)
    params_dashboard(params)
    trial_param_list = trial_params(params)

    dt = datetime.now()
    timestamp = dt.strftime("%Y-%m-%d-%H-%M-%S")

    if args.num_procs == 1:
        for param in trial_param_list:
            param["experiment_time"]=timestamp
            run_trial(args.device,param)
    else:
        with Pool(processes=args.num_procs) as pool:
            for param in trial_param_list:
                param["experiment_time"]=timestamp
                pool.apply_async(run_trial,(args.device,param,))
            
            pool.close()
            pool.join()

    
