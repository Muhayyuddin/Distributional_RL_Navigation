import sys
sys.path.insert(0,"./thirdparty")
from stable_baselines3 import PPO
from stable_baselines3 import A2C
from stable_baselines3 import DQN
from thirdparty import QRDQN
from thirdparty import IQNAgent
import APF
import BA
import os
import gym
import marinenav_env.envs.marinenav_env as marinenav_env
import numpy as np
import copy
import scipy.spatial
import env_visualizer
import json
from datetime import datetime

def evaluation_IQN(first_observation, agent, test_env, adaptive:bool=False):
    observation = first_observation
    cumulative_reward = 0.0
    length = 0
    done = False
    energy = 0.0
    
    quantiles_data = []
    taus_data = []

    cvars = [1.0]

    while not done and length < 1000:
        action = None
        select = 0
        for i,cvar in enumerate(cvars):
            if adaptive:
                a, quantiles, taus = agent.act_adaptive_eval(observation)
            else:
                a, quantiles, taus = agent.act_eval(observation,cvar=cvar)

            if i == select:
                action = a

            if len(quantiles_data) < len(cvars):
                quantiles_data.append(quantiles)
                taus_data.append(taus)
            else:
                quantiles_data[i] = np.concatenate((quantiles_data[i],quantiles))
                taus_data[i] = np.concatenate((taus_data[i],taus))
        
        observation, reward, done, info = test_env.step(int(action))
        cumulative_reward += test_env.discount ** length * reward
        length += 1
        energy += test_env.robot.compute_action_energy_cost(int(action))
        
    # metric data
    success = True if info["state"] == "reach goal" else False
    time = test_env.robot.dt * test_env.robot.N * length

    ep_data = test_env.episode_data()
    ep_data["robot"]["actions_cvars"] = copy.deepcopy(cvars)
    ep_data["robot"]["actions_quantiles"] = [x.tolist() for x in quantiles_data]
    ep_data["robot"]["actions_taus"] = [x.tolist() for x in taus_data]

    return ep_data, success, time, energy

def evaluation_DQN(first_observation, agent, test_env):
    observation = first_observation
    cumulative_reward = 0.0
    length = 0
    done = False
    energy = 0.0

    while not done and length < 1000:
        action, _ = agent.predict(observation,deterministic=True)
        observation, reward, done, info = test_env.step(int(action))
        cumulative_reward += test_env.discount ** length * reward
        length += 1
        energy += test_env.robot.compute_action_energy_cost(int(action))
        
    # metric data
    success = True if info["state"] == "reach goal" else False
    time = test_env.robot.dt * test_env.robot.N * length

    return test_env.episode_data(), success, time, energy

def evaluation_classical(first_observation, agent, test_env):
    observation = first_observation
    cumulative_reward = 0.0
    length = 0
    done = False
    energy = 0.0
    
    while not done and length < 1000:
        action = agent.act(observation)
        observation, reward, done, info = test_env.step(int(action))
        cumulative_reward += test_env.discount ** length * reward
        length += 1
        energy += test_env.robot.compute_action_energy_cost(int(action))

    # metric data
    success = True if info["state"] == "reach goal" else False
    time = test_env.robot.dt * test_env.robot.N * length

    return test_env.episode_data(), success, time, energy

def exp_setup_1(envs):
    # keep default env settings
    pass

def exp_setup_2(envs):
    # fix the obstacle r = 0.5, and increases num to 10
    for env in envs:
        env.obs_r_range = [1,1]
        env.num_obs = 10

def exp_setup_3(envs):
    # 1. fix the obstacle r = 0.5, and increases num to 10
    # 2. reduce the area of obstacle generation to make them more dense
    # 3. fix the start and goal position so that obstacles lie in the line between them
    for env in envs:
        env.obs_r_range = [1,1]
        env.num_obs = 10

def exp_setup_4(envs):
    # Demonstrate that RL agents are clearly better in adverse flow field
    observations = []

    for test_env in envs:
        test_env.cores.clear()
        test_env.obstacles.clear()
        
        # set start and goal
        test_env.start = np.array([15.0,10.0])
        test_env.goal = np.array([45.0,35.0])

        # set vortex cores data
        core_0 = marinenav_env.Core(14.0,1.0,0,np.pi*10.0)
        core_1 = marinenav_env.Core(10.0,18.0,0,np.pi*7.0)
        core_2 = marinenav_env.Core(15.0,26.0,1,np.pi*8.0)
        core_3 = marinenav_env.Core(25.0,23.0,1,np.pi*10.0)
        core_4 = marinenav_env.Core(13.0,41.0,0,np.pi*8.0)
        core_5 = marinenav_env.Core(40.0,22.0,0,np.pi*8.0)
        core_6 = marinenav_env.Core(36.0,30.0,0,np.pi*7.0)
        core_7 = marinenav_env.Core(37.0,37.0,1,np.pi*6.0)

        test_env.cores = [core_0,core_1,core_2,core_3, \
                        core_4,core_5,core_6,core_7]

        centers = None
        for core in test_env.cores:
            if centers is None:
                centers = np.array([[core.x,core.y]])
            else:
                c = np.array([[core.x,core.y]])
                centers = np.vstack((centers,c))
        
        if centers is not None:
            test_env.core_centers = scipy.spatial.KDTree(centers)

        # set obstacles
        obs_1 = marinenav_env.Obstacle(20.0,36.0,1.5)
        obs_2 = marinenav_env.Obstacle(35.0,19.0,1.5)
        obs_3 = marinenav_env.Obstacle(8.0,25.0,1.5)
        obs_4 = marinenav_env.Obstacle(30,33.0,1.5)

        test_env.obstacles = [obs_1,obs_2,obs_3,obs_4]

        centers = None
        for obs in test_env.obstacles:
            if centers is None:
                centers = np.array([[obs.x,obs.y]])
            else:
                c = np.array([[obs.x,obs.y]])
                centers = np.vstack((centers,c))
        
        # KDTree storing obstacle center positions
        if centers is not None: 
            test_env.obs_centers = scipy.spatial.KDTree(centers)

        # reset robot
        test_env.robot.init_theta = 3 * np.pi / 4
        test_env.robot.init_speed = 1.0
        current_v = test_env.get_velocity(test_env.start[0],test_env.start[1])
        test_env.robot.reset_state(test_env.start[0],test_env.start[1], current_velocity=current_v)

        observations.append(test_env.get_observation())

    return observations

def run_experiment():
    num = 1
    agents = [IQN_agent_0,IQN_agent_1,DQN_agent_1,APF_agent,BA_agent]
    names = ["adaptive_IQN","IQN","DQN","APF","BA"]
    envs = [test_env_0,test_env_1,test_env_3,test_env_5,test_env_6]
    evaluations = [evaluation_IQN,evaluation_IQN,evaluation_DQN, \
                   evaluation_classical,evaluation_classical]

    dt = datetime.now()
    timestamp = dt.strftime("%Y-%m-%d-%H-%M-%S")

    observations = exp_setup_4(envs)

    exp_data = {}
    for name in names:
        exp_data[name] = dict(ep_data=[],success=[],time=[],energy=[])

    print(f"Running {num} experiments\n")
    for i in range(num):
        for j in range(len(agents)):
            agent = agents[j]
            env = envs[j]
            evaluation = evaluations[j]
            name = names[j]
            
            # obs = env.reset()
            obs = observations[j]
            
            if name == "adaptive_IQN":
                ep_data, success, time, energy = evaluation(obs,agent,env,adaptive=True)
            else:
                ep_data, success, time, energy = evaluation(obs,agent,env)
            
            exp_data[name]["ep_data"].append(ep_data)
            exp_data[name]["success"].append(success)
            exp_data[name]["time"].append(time)
            exp_data[name]["energy"].append(energy)


        if (i+1) % 10 == 0:
            print(f"=== Finish {i+1} experiments ===")

            for k in range(len(agents)):
                name = names[k]
                res = np.array(exp_data[name]["success"])
                idx = np.where(res == 1)[0]
                rate = np.sum(res)/(i+1)
                
                t = np.array(exp_data[name]["time"])
                e = np.array(exp_data[name]["energy"])
                avg_t = np.mean(t[idx])
                avg_e = np.mean(e[idx])
                print(f"{name} | success rate: {rate:.2f} | avg_time: {avg_t:.2f} | avg_energy: {avg_e:.2f}")
            
            print("\n")

            filename = f"experiment_data/exp_data_{timestamp}.json"
            with open(filename,"w") as file:
                json.dump(exp_data,file)

if __name__ == "__main__":
    seed = 15 # PRNG seed for all testing envs

    ##### adaptive IQN #####
    test_env_0 = marinenav_env.MarineNavEnv(seed)

    save_dir = "training_data/experiment_2022-12-23-18-02-05/seed_2"

    device = "cuda:0"

    IQN_agent_0 = IQNAgent(test_env_0.get_state_space_dimension(),
                         test_env_0.get_action_space_dimension(),
                         device=device,
                         seed=2)
    IQN_agent_0.load_model(save_dir,device)
    ##### adaptive IQN #####
    

    ##### IQN cvar = 1.0 #####
    test_env_1 = marinenav_env.MarineNavEnv(seed)

    save_dir = "training_data/experiment_2022-12-23-18-02-05/seed_2"

    device = "cuda:0"

    IQN_agent_1 = IQNAgent(test_env_1.get_state_space_dimension(),
                         test_env_1.get_action_space_dimension(),
                         device=device,
                         seed=2)
    IQN_agent_1.load_model(save_dir,device)
    ##### IQN cvar = 1.0 #####


    ##### DQN #####
    test_env_3 = marinenav_env.MarineNavEnv(seed)
    
    save_dir = "training_data/experiment_2022-12-23-18-19-03/seed_2"
    model_file = "latest_model.zip"

    DQN_agent_1 = DQN.load(os.path.join(save_dir,model_file),print_system_info=False)
    ##### DQN #####


    ##### APF #####
    test_env_5 = marinenav_env.MarineNavEnv(seed)
    
    APF_agent = APF.APF_agent(test_env_5.robot.a,test_env_5.robot.w)
    ##### APF #####


    ##### BA #####
    test_env_6 = marinenav_env.MarineNavEnv(seed)
    
    BA_agent = BA.BA_agent(test_env_6.robot.a,test_env_6.robot.w)
    ##### BA #####

    run_experiment()
