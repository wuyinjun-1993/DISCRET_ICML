from collections import namedtuple, deque
import random
import torch
import os, sys
from torch import nn, optim

from functools import reduce
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from GRU_ODE.models import NNFOwithBayesianJumps_causal_rl, NNFOwithBayesianJumps_causal_rl2, agg_op_id_key, agg_op_str_key,agg_op_key, agg_Q_key, min_time_Q_key, max_time_Q_key

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from rl_models.enc_dec import pred_probs_key, pred_Q_key, pred_v_key, prev_prog_key, col_id_key, select_num_feat_key, col_Q_key, col_probs_key, op_key, op_id_key, col_key, outbound_key, min_Q_val, mask_atom_representation_for_op0, mask_atom_representation1, down_weight_removed_feats


Transition = namedtuple("Transition", ("features", "data", "program", "action", "next_program", "reward"))

class ReplayMemory:
  def __init__(self, capacity):
    self.capacity = capacity
    self.memory = deque([], maxlen=capacity)

  def push(self, transition):
    if len(self.memory) >= self.capacity:
        item = self.memory.popleft()
        del item

    self.memory.append(transition)

  def sample(self, batch_size):
    return random.sample(self.memory, batch_size)

  def __len__(self):
    return len(self.memory)

class DQN_all_temporal:
    def __init__(self, device,unique_treatment_label_ls, lang, replay_memory_capacity, learning_rate, batch_size, gamma, program_max_len, dropout_p, feat_range_mappings, mem_sample_size=1, seed=0, numeric_count=None, category_count=None, category_sum_count = None, has_embeddings=False, model="mlp", topk_act=1, model_config=None, rl_config=None, feat_group_names = None, removed_feat_ls=None, prefer_smaller_range = False, prefer_smaller_range_coeff=0.5, method_two=False, args = None, work_dir = None):
        self.mem_sample_size = mem_sample_size
        self.batch_size = batch_size
        self.gamma = gamma
        self.lang = lang
        torch.manual_seed(seed)
        self.topk_act = topk_act
        torch.manual_seed(seed)
        params_dict = args.params_dict
        self.weighted_reward = args.weighted_reward
        
        if args.method_one:
            self.policy_net = NNFOwithBayesianJumps_causal_rl(args, rl_config["discretize_feat_value_count"], lang, program_max_len, model_config["latent_size"], dropout_p, numeric_count, category_sum_count, feat_range_mappings, input_size = params_dict["input_size"], hidden_size = params_dict["hidden_size"],
                                            p_hidden = params_dict["p_hidden"], prep_hidden = params_dict["prep_hidden"],
                                            logvar = params_dict["logvar"], mixing = params_dict["mixing"],
                                            full_gru_ode = params_dict["full_gru_ode"],
                                            solver = params_dict["solver"], impute = params_dict["impute"], treatment_class_count = len(unique_treatment_label_ls), topk_act=args.topk_act, device=device, is_log = args.is_log, work_dir = work_dir, removed_feat_ls=removed_feat_ls, reward_specifity=args.reward_specifity)
    
            self.target_net = NNFOwithBayesianJumps_causal_rl(args, rl_config["discretize_feat_value_count"], lang, program_max_len, model_config["latent_size"], dropout_p, numeric_count, category_sum_count, feat_range_mappings, input_size = params_dict["input_size"], hidden_size = params_dict["hidden_size"],
                                                p_hidden = params_dict["p_hidden"], prep_hidden = params_dict["prep_hidden"],
                                                logvar = params_dict["logvar"], mixing = params_dict["mixing"],
                                                full_gru_ode = params_dict["full_gru_ode"],
                                                solver = params_dict["solver"], impute = params_dict["impute"], treatment_class_count = len(unique_treatment_label_ls), topk_act=args.topk_act, device=device, is_log = args.is_log, work_dir = work_dir, removed_feat_ls=removed_feat_ls, reward_specifity=args.reward_specifity)
        
        else:
            self.policy_net = NNFOwithBayesianJumps_causal_rl2(args, rl_config["discretize_feat_value_count"], lang, program_max_len, model_config["latent_size"], dropout_p, numeric_count, category_sum_count, feat_range_mappings, input_size = params_dict["input_size"], hidden_size = params_dict["hidden_size"],
                                                p_hidden = params_dict["p_hidden"], prep_hidden = params_dict["prep_hidden"],
                                                logvar = params_dict["logvar"], mixing = params_dict["mixing"],
                                                full_gru_ode = params_dict["full_gru_ode"],
                                                solver = params_dict["solver"], impute = params_dict["impute"], treatment_class_count = len(unique_treatment_label_ls), topk_act=args.topk_act, device=device, is_log = args.is_log, work_dir = work_dir, removed_feat_ls=removed_feat_ls, reward_specifity=args.reward_specifity)
        
            self.target_net = NNFOwithBayesianJumps_causal_rl2(args, rl_config["discretize_feat_value_count"], lang, program_max_len, model_config["latent_size"], dropout_p, numeric_count, category_sum_count, feat_range_mappings, input_size = params_dict["input_size"], hidden_size = params_dict["hidden_size"],
                                                p_hidden = params_dict["p_hidden"], prep_hidden = params_dict["prep_hidden"],
                                                logvar = params_dict["logvar"], mixing = params_dict["mixing"],
                                                full_gru_ode = params_dict["full_gru_ode"],
                                                solver = params_dict["solver"], impute = params_dict["impute"], treatment_class_count = len(unique_treatment_label_ls), topk_act=args.topk_act, device=device, is_log = args.is_log, work_dir = work_dir, removed_feat_ls=removed_feat_ls, reward_specifity=args.reward_specifity)
        
        
        # self.do_medical = args.do_medical
        # if not args.do_medical:
        #     if model == "mlp":
        #         self.policy_net = RLSynthesizerNetwork_mlp2(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], dropout_p=dropout_p, num_feat_count=numeric_count, category_sum_count=category_sum_count, feat_range_mappings=feat_range_mappings, topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff=prefer_smaller_range_coeff, args = args)
        #     else:
        #         self.policy_net = RLSynthesizerNetwork_transformer(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], tf_latent_size=model_config["tf_latent_size"], dropout_p=dropout_p, feat_range_mappings=feat_range_mappings, numeric_count=numeric_count, category_count=category_count, has_embeddings=has_embeddings, pretrained_model_path=model_config["pretrained_model_path"], topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, method_two=method_two, args = args)
            
        #     if model == "mlp":
        #         self.target_net = RLSynthesizerNetwork_mlp2(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], dropout_p = 0, num_feat_count=numeric_count, category_sum_count=category_sum_count, feat_range_mappings=feat_range_mappings, topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range= prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, args = args)
        #     else:
        #         self.target_net = RLSynthesizerNetwork_transformer(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], tf_latent_size=model_config["tf_latent_size"], dropout_p = 0, feat_range_mappings=feat_range_mappings, numeric_count=numeric_count, category_count=category_count, has_embeddings=has_embeddings, pretrained_model_path=model_config["pretrained_model_path"], topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range=prefer_smaller_range, prefer_smaller_range_coeff=prefer_smaller_range_coeff, method_two=method_two, args = args)
        # else:
        #     if model == "mlp":
        #         self.policy_net = RLSynthesizerNetwork_mlp0(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], dropout_p=dropout_p, category_sum_count=category_sum_count, feat_range_mappings=feat_range_mappings, topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff=prefer_smaller_range_coeff, args = args)
        #     else:
        #         self.policy_net = RLSynthesizerNetwork_transformer0(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], tf_latent_size=model_config["tf_latent_size"], dropout_p=dropout_p, feat_range_mappings=feat_range_mappings, numeric_count=numeric_count, category_count=category_count, category_sum_count=category_sum_count, has_embeddings=has_embeddings, pretrained_model_path=model_config["pretrained_model_path"], topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, method_two=method_two, args = args)
            
        #     if model == "mlp":
        #         self.target_net = RLSynthesizerNetwork_mlp0(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], dropout_p = 0, category_sum_count=category_sum_count, feat_range_mappings=feat_range_mappings, topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range= prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, args = args)
        #     else:
        #         self.target_net = RLSynthesizerNetwork_transformer0(lang=lang, program_max_len=program_max_len,latent_size=model_config["latent_size"], tf_latent_size=model_config["tf_latent_size"], dropout_p = 0, feat_range_mappings=feat_range_mappings, numeric_count=numeric_count, category_count=category_count, category_sum_count=category_sum_count, has_embeddings=has_embeddings, pretrained_model_path=model_config["pretrained_model_path"], topk_act=topk_act, feat_group_names=feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range=prefer_smaller_range, prefer_smaller_range_coeff=prefer_smaller_range_coeff, method_two=method_two, args = args)

        self.params_dict = args.params_dict 
        self.target_net.load_state_dict(self.policy_net.state_dict())
        for p in self.target_net.parameters():
            p.requires_grad = False

        self.memory = ReplayMemory(replay_memory_capacity)

        self.criterion = nn.SmoothL1Loss()
        self.optimizer = optim.Adam(self.policy_net.parameters(), learning_rate)
        self.device = device
        
        self.policy_net = self.policy_net.to(device)
        self.target_net = self.target_net.to(device)
        
        
    #turns atom into one-hot encoding
    def atom_to_vector(self, atom:dict):
        return self.policy_net.atom_to_vector(atom)

    def atom_to_vector_ls(self, atom:dict):
        return self.policy_net.atom_to_vector_ls(atom)

    def atom_to_vector_ls0(self, atom):
        return self.policy_net.atom_to_vector_ls0(atom)

    def vector_ls_to_str_ls0(self, atom):
        return self.policy_net.vector_ls_to_str0(atom)

    def vector_to_atom(self, vec):
        return self.policy_net.vector_to_atom(vec)

    #turns network Grammar Networks predictions and turns them into an atom
    def prediction_to_atom(self, pred:dict):
        return self.policy_net.prediction_to_atom(pred)

    def random_atom(self, program):
        #TODO
        if len(program) == 0:
            pred = self.policy_net.random_atom(program = [torch.tensor([0]*self.policy_net.ATOM_VEC_LENGTH, device=self.device, dtype=torch.float)])
        else:
            pred = self.policy_net.random_atom(program = program)
        return self.policy_net.prediction_to_atom(pred)

    def predict_atom(self, features, X_pd, program, epsilon):
        if len(program) == 0:
            pred = self.policy_net(features, X_pd, [self.first_prog_embed], ["formula"], epsilon)
        else:
            #program.sort()
            pred = self.policy_net(features, X_pd, program, ["formula"], epsilon)
        return self.policy_net.prediction_to_atom(pred), pred
    
    def predict_atom_ls(self, data, X_pd_ls, epsilon, id_attr, time_attr, trainer, train=False, time_ptr_val=None, obs_idx_val=None, outcome_arr_val=None, X_pd_val=None, all_times_val = None):
        all_other_pats_pd_full, pid_ls, X_pd_full, obs_idx, cov, X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask, all_other_pats_ls, all_other_pats_ids_ls_ls, numer_feat_ls, cat_feat_ls, unique_times_val, treatment_arr_val = data
        
        return  self.policy_net.forward(all_other_pats_pd_full, pid_ls, trainer, X_pd_ls, all_other_pats_ls, all_other_pats_ids_ls_ls, X_pd_full, times, time_ptr, X, M, obs_idx, treatment_arr, outcome_arr, delta_t=self.params_dict["delta_t"], T=self.params_dict["T"], cov=cov, return_path=False, epsilon=epsilon, init=True, id_attr=id_attr, time_attr=time_attr, numer_feat_ls=numer_feat_ls, cat_feat_ls=cat_feat_ls, train=train, treatment_arr_val=treatment_arr_val, times_val=unique_times_val, time_ptr_val=time_ptr_val, obs_idx_val=obs_idx_val, outcome_arr_val=outcome_arr_val, X_pd_val=X_pd_val, all_times_val=all_times_val)
        
        # if len(program) == 0:
        #     # init_program = self.first_prog_embed.unsqueeze(0).repeat(len(X_pd_ls), self.topk_act, 1)
        #     init_program = self.first_prog_embed.unsqueeze(0).repeat(len(X), 1)
        #     # times, time_ptr, X, M, obs_idx, treatment_arr, outcome_arr, delta_t, T, cov,
        #         # return_path=False, smoother = False, class_criterion = None, labels=None, times_val=None, treatment_arr_val=None
        #         # (times, time_ptr, X, M, obs_idx, treatment_arr, outcome_arr, delta_t=delta_t, T=T, cov=cov, return_path=False)
        #     pred = self.policy_net.forward(trainer, X_pd_ls, all_other_pats_ls, X_pd_full, times, time_ptr, X, M, obs_idx, treatment_arr, outcome_arr, delta_t=self.params_dict["delta_t"], T=self.params_dict["T"], cov=cov, return_path=False, program=[init_program], outbound_mask_ls=outbound_mask_ls, epsilon=epsilon, init=True, id_attr=id_attr, time_attr=time_attr, program_str=program_str, program_col_ls=program_col_ls)
        #     del init_program
        # else:
        #     #program.sort()
        #     pred = self.policy_net.forward(features, X_pd_ls, program, outbound_mask_ls, ["formula"], epsilon)
        # return self.policy_net.prediction_to_atom_ls(pred), pred
        # return pred
    
    #predicts the best atom to add to the program from the given next state, and provides the maximal tensors which produced that decision
    #uses target net!!!
    # def predict_next_state_with_tensor_info(self, features, program):
    #     if len(program) == 0:
    #         pred = self.target_net(features, [self.first_prog_embed], ["formula"], 0)
    #     else:
    #         #program.sort()
    #         pred = self.target_net(features, program, ["formula"], 0)
    #     max_tensors = {token:torch.max(token_val).reshape((1,1)) for token, token_val in pred.items()}
    #     return self.target_net.prediction_to_atom(pred), max_tensors

    def predict_next_state_with_tensor_info(self, features, data, program):
        if len(program) == 0:
            pred = self.target_net(features, data, [self.first_prog_embed], ["formula"], 0)
        else:
            #program.sort()
            pred = self.target_net(features, data, program, ["formula"], 0)
        max_tensors = dict()
        for token, token_val in pred.items():
            if not self.policy_net.get_prefix(token) in self.lang.syntax["num_feat"]:
                max_tensors[token] = torch.max(token_val).reshape((1,1))
            else:
                if token.endswith("_ub"):
                    # max_tensors[token] = [torch.max(token_val[1][0]).reshape((1,1)), torch.max(token_val[1][1]).reshape((1,1))]
                    max_tensors[self.policy_net.get_prefix(token)] = torch.max(token_val[1]).reshape(1,1)
        
        # max_tensors = {token:torch.max(token_val).reshape((1,1)) for token, token_val in pred.items() if not token in self.lang.syntax["num_feat"]}
        
        return self.target_net.prediction_to_atom(pred), max_tensors
    
    def predict_next_state_with_tensor_info_ls(self, features, data, program):
        if len(program) == 0:
            init_program = self.first_prog_embed.unsqueeze(0).repeat(len(data),1)
            pred = self.target_net.forward_ls(features, data, [init_program], ["formula"], 0, replay=True)
            del init_program
        else:
            #program.sort()
            pred = self.target_net.forward_ls(features, data, program, ["formula"], 0, replay=True)
        max_tensors = dict()
        for token, token_val in pred.items():
            # if not token in self.lang.syntax["num_feat"]:
            if not type(token) is tuple:
                max_tensors[token] = torch.max(token_val, dim=1)[0].reshape((len(data),1))
            else:
                if not "pred_score" in max_tensors:
                    max_tensors["pred_score"] = [torch.zeros(len(data), device = self.device), torch.zeros(len(data), device = self.device)]
                pred_val = pred[token]
                for token_key in token:
                    
                    # token_key = token_key[0]
                    probs = pred_val[1][token_key]
                    # ub_probs = pred_val[1][token_key][1]
                    sample_ids = token_val[2][token_key].view(-1)
                    sample_cln_id_ls = token_val[3][token_key]
                    val = probs[torch.tensor(list(range(len(sample_ids)))), sample_cln_id_ls[0].view(-1)]
                    if token_key.endswith("_lb"):
                        max_tensors["pred_score"][0][sample_ids] = val
                    elif token_key.endswith("_ub"):
                        max_tensors["pred_score"][1][sample_ids] = val
                    del val
                    # val = ub_probs[torch.tensor(list(range(len(sample_ids)))), sample_cln_id_ls[1].view(-1)]      
                    # max_tensors[token][1][sample_ids] = val
                    # del val
                # print()
                # max_tensors[token] = [torch.max(token_val[1][0]).reshape((1,1)), torch.max(token_val[1][1]).reshape((1,1))]
        
        # max_tensors = {token:torch.max(token_val).reshape((1,1)) for token, token_val in pred.items() if not token in self.lang.syntax["num_feat"]}
        return_pred = self.target_net.prediction_to_atom_ls(pred)
        del pred
        return return_pred, max_tensors
    
    
    def predict_next_state_with_tensor_info_ls0(self, features, data, state, other_info):
        program, outbound_mask_ls, program_str, program_col_ls, res_all_other_pat_ls = state
        X, M, obs_idx, time_ptr, pid_ls, h0, p0, i, tid0, all_other_pats_ls, all_other_pats_ids_ls_ls, X_pd_ls, all_other_pats_pd_full = features
        # program, outbound_mask_ls = state
        start = time_ptr[i]
        end = time_ptr[i+1]
        i_obs = obs_idx[start:end]

        epsilon, id_attr, time_attr, numer_feat_ls, cat_feat_onehot_ls, delta_t, arr_idx, trainer, prev_time, current_time, obs_time, treatment_arr, outcome_arr = other_info
        if arr_idx == 1 and i == 2:
            print()
        pred, _ = self.target_net.forward_single_time_step_single_predicate(all_other_pats_pd_full, prev_time, current_time, tid0, X, M, obs_idx, outcome_arr, i, time_ptr, treatment_arr, obs_time, delta_t, arr_idx, trainer, pid_ls, h0, p0, epsilon, id_attr, time_attr, data, all_other_pats_ls, all_other_pats_ids_ls_ls, program, program_str, program_col_ls, X_pd_ls, outbound_mask_ls, res_all_other_pat_ls, numer_feat_ls, cat_feat_onehot_ls,None, None, return_reward=False, atom_sub_ls=None, eval=True)
        
        # if len(program) == 0:
        # forward_ls0(features, X_pd, [init_program], queue, 0, eval=True, replay=True, existing_atom=origin_atom)
        #     init_program = self.first_prog_embed.unsqueeze(0).repeat(len(data), 1)
        #     pred = self.target_net.forward_ls0(features, data, [init_program], outbound_mask_ls, ["formula"], 0, eval=False, init=True)
        #     del init_program
        # else:
        #     #program.sort()
        #     pred = self.target_net.forward_ls0(features, data, program, outbound_mask_ls, ["formula"], 0, eval=False)
        max_tensors_ls = []
        for idx in range(len(pred)):
            max_tensors,_ = pred[idx][pred_Q_key].max(dim=-1)

            # max_tensors = torch.mean(max_tensors, dim=-1)

            max_col_tensors,_ = torch.topk(pred[idx][col_Q_key].view(len(pred[idx][col_Q_key]), -1), k = self.topk_act, dim=-1)#.max(dim=-1)

            max_min_time_tensors, _ = pred[idx][min_time_Q_key].max(dim=-1)

            max_agg_op_tensors,_ = pred[idx][agg_Q_key].max(dim=-1)

            # max_col_tensors  =torch.mean(max_col_tensors, dim=-1)
            selected_num_feat_tensor_bool = pred[idx][select_num_feat_key]
            # if op_Q_key in pred:

            #     max_op_tensors,_ = pred[op_Q_key].max(dim=-1)

            #     # max_op_tensors = torch.mean(max_op_tensors, dim=-1)

            #     max_tensors += max_col_tensors + max_op_tensors

            #     max_tensors = max_tensors/3
            
            # else:
            # max_op_tensors,_ = pred[op_Q_key].max(dim=-1)

            # max_op_tensors = torch.mean(max_op_tensors, dim=-1)

            numeric_tensors = (max_tensors + max_col_tensors + max_min_time_tensors + max_agg_op_tensors)/4

            cat_tensors = (max_col_tensors + max_agg_op_tensors + max_min_time_tensors)/3

            # max_tensors += max_col_tensors

            # max_tensors += max_min_time_tensors

            # max_tensors += max_agg_op_tensors

            # max_tensors = max_tensors/4
                
            final_tensors = numeric_tensors*selected_num_feat_tensor_bool + cat_tensors*(1-selected_num_feat_tensor_bool)
            # final_tensors = torch.mean(final_tensors, dim=-1)
            max_tensors_ls.append(final_tensors[i_obs])
            # max_tensors = dict()
            # for token, token_val in pred.items():
            #     # if not token in self.lang.syntax["num_feat"]:
            #     if not type(token) is tuple:
            #         max_tensors[token] = torch.max(token_val, dim=1)[0].reshape((len(data),1))
            #     else:
            #         if not "pred_score" in max_tensors:
            #         pred_val = pred[token]
            #         for token_key in token:
                        
            #             # token_key = token_key[0]
            #             probs = pred_val[1][token_key]
            #             # ub_probs = pred_val[1][token_key][1]
            #             sample_ids = token_val[2][token_key].view(-1)
            #             sample_cln_id_ls = token_val[3][token_key]
            #             val = probs[torch.tensor(list(range(len(sample_ids)))), sample_cln_id_ls[0].view(-1)]
            #             if token_key.endswith("_lb"):
            #                 max_tensors["pred_score"][0][sample_ids] = val
            #             elif token_key.endswith("_ub"):
            #                 max_tensors["pred_score"][1][sample_ids] = val
            #             del val
            #             # val = ub_probs[torch.tensor(list(range(len(sample_ids)))), sample_cln_id_ls[1].view(-1)]      
            #             # max_tensors[token][1][sample_ids] = val
            #             # del val
            #         # print()
            #         # max_tensors[token] = [torch.max(token_val[1][0]).reshape((1,1)), torch.max(token_val[1][1]).reshape((1,1))]
            
            # # max_tensors = {token:torch.max(token_val).reshape((1,1)) for token, token_val in pred.items() if not token in self.lang.syntax["num_feat"]}
            # return_pred = self.target_net.prediction_to_atom_ls(pred)
            # del pred
            # return return_pred, max_tensors
        return torch.mean(torch.stack(max_tensors_ls, dim=1).to(self.device), dim=-1)
    
    def predict_next_state_with_tensor_info_ls0_medical(self, features, data, state):
        program = state
        
        if len(state) == 0:
            init_program = self.first_prog_embed.unsqueeze(0).repeat(len(data), 1)
            pred = self.target_net.forward_ls0(features, data, [init_program], ["formula"], 0, eval=False, init=True)
            del init_program
        else:
            #program.sort()
            pred = self.target_net.forward_ls0(features, data, program, ["formula"], 0, eval=False)
            
        # max_tensors,_ = pred[pred_Q_key].max(dim=-1)

        # max_tensors = torch.mean(max_tensors, dim=-1)

        max_col_tensors,_ = torch.topk(pred[col_Q_key].view(len(pred[col_Q_key]), -1), k = self.topk_act, dim=-1)#.max(dim=-1)

        # max_col_tensors  =torch.mean(max_col_tensors, dim=-1)

        # if op_Q_key in pred:

        #     max_op_tensors,_ = pred[op_Q_key].max(dim=-1)

        #     # max_op_tensors = torch.mean(max_op_tensors, dim=-1)

        #     max_tensors += max_col_tensors + max_op_tensors

        #     max_tensors = max_tensors/3
        
        # else:
        #     # max_op_tensors,_ = pred[op_Q_key].max(dim=-1)

        #     # max_op_tensors = torch.mean(max_op_tensors, dim=-1)

        #     max_tensors += max_col_tensors

        #     max_tensors = max_tensors/2

        return max_col_tensors.to(self.device)

    #takes a state,action (where action is an atom) pair and returns prediction tensors which are generated when picking the same tokens from the given atom
    # def get_state_action_prediction_tensors(self, features, program, atom):
    #     queue = list(atom.keys())
    #     if len(program) == 0:
    #         pred = self.policy_net(features, [self.first_prog_embed], queue, 0)
    #     else:
    #         #program.sort()
    #         pred = self.policy_net(features, program, queue, 0)

    #     tensor_indeces = {token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
    #     atom_prediction_tensors = {token:pred[token].view(-1)[tensor_idx].reshape((1,1)) for token, tensor_idx in tensor_indeces.items()}
    #     return atom_prediction_tensors
    
    def get_state_action_prediction_tensors(self, features, X_pd, program, atom_ls):
        atom, origin_atom = atom_ls
        queue = list(atom.keys())
        if len(program) == 0:
            pred = self.policy_net(features, X_pd, [self.first_prog_embed], queue, 0, eval=True, existing_atom=origin_atom)
        else:
            #program.sort()
            pred = self.policy_net(features, X_pd, program, queue, 0, eval=True, existing_atom=origin_atom)

        tensor_indeces = {}#{token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
        for token, token_val in atom.items():
            if token == "num_op" or token.endswith("_prob"):
                continue

            if self.policy_net.get_prefix(token) not in self.lang.syntax["num_feat"]:
                # if not token.endswith("_prob"):
                    tensor_indeces[token] = self.policy_net.grammar_token_val_to_num[token][token_val]
            else:
                # tensor_indeces[token] = [torch.argmax(atom[token][1][0]).item(),torch.argmax(atom[token][1][1]).item()]
                tensor_indeces[token] = torch.argmax(atom[token][1]).item()
            # else:
            #     tensor_indeces[token] = 0
        atom_prediction_tensors = {}
        for token, tensor_idx in tensor_indeces.items():
            if self.policy_net.get_prefix(token) not in self.lang.syntax["num_feat"]:
                atom_prediction_tensors[token] = pred[token].view(-1)[tensor_idx].reshape((1,1))
            else:
                if token.endswith("_ub"):
                    atom_prediction_tensors[self.policy_net.get_prefix(token)] = pred[token][1][tensor_idx].view(-1)
                # atom_prediction_tensors[token] = [pred[token][1][0][tensor_idx[0]].view(-1).reshape((1,1)),pred[token][1][1][tensor_idx[1]].view(-1).reshape((1,1))]#.view(-1).reshape((1,1))
            
        # {token:pred[token].view(-1)[tensor_idx].reshape((1,1)) for token, tensor_idx in tensor_indeces.items()}
        return atom_prediction_tensors

    # def get_state_action_prediction_tensors_ls(self, features, X_pd, program, atom_pair):
    #     atom = atom_pair[0]
    #     origin_atom = atom_pair[1]
    #     queue = list(atom.keys())
    #     if len(program) == 0:
    #         init_program = self.first_prog_embed.unsqueeze(0).repeat(len(X_pd),1)
    #         pred = self.policy_net.forward_ls(features, X_pd, [init_program], queue, 0, eval=True, replay=True, existing_atom=origin_atom)
    #         del init_program
    #     else:
    #         #program.sort()
    #         pred = self.policy_net.forward_ls(features, X_pd, program, queue, 0, eval=True, replay=True, existing_atom=origin_atom)

    #     tensor_indeces = {}#{token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
    #     atom_prediction_tensors = {}
    #     for token, token_val in atom.items():
    #         # if token == "num_op" or token.endswith("_prob"):
    #         #     continue

    #         # if token not in self.lang.syntax["num_feat"]:
    #         if not type(token) is tuple:
    #             # if not token.endswith("_prob"):
    #                 # tensor_indeces[token] = self.policy_net.grammar_token_val_to_num[token][token_val]
    #                 if not type(token_val) is dict:
    #                     tensor_idx = self.policy_net.grammar_token_val_to_num[token][token_val]
    #                     val = pred[token][:,tensor_idx].reshape((len(X_pd),1))
    #                     atom_prediction_tensors[token] = val
    #                     del val
    #                 else:
    #                     for token_val_key in token_val:
    #                         token_val_sample_ids = token_val[token_val_key]
    #                         tensor_idx = self.policy_net.grammar_token_val_to_num[token][token_val_key]
    #                         val = pred[token][token_val_sample_ids,tensor_idx]
    #                         atom_prediction_tensors[token][token_val_sample_ids] = val
    #                         del val
                        
    #         else:
    #             if not "pred_score" in atom_prediction_tensors:
    #             pred_val = pred[token]
    #             for token_key in token:
                    
    #                 # token_key = token_key[0]
    #                 # lb_probs = pred_val[1][token_key][0]
    #                 probs = pred_val[1][token_key]
    #                 sample_ids = token_val[2][token_key].view(-1)
    #                 sample_cln_id_ls = token_val[3][token_key]
    #                 val = probs[sample_ids.view(-1), sample_cln_id_ls.view(-1)]
    #                 if token_key.endswith("_lb"):
    #                     atom_prediction_tensors["pred_score"][0][sample_ids] = val
    #                 elif token_key.endswith("_ub"):
    #                     atom_prediction_tensors["pred_score"][1][sample_ids] = val
    #                 del val
    #                 # val = ub_probs[sample_ids.view(-1), sample_cln_id_ls[1].view(-1)]
    #                 # atom_prediction_tensors[token][1][sample_ids] = val
    #                 # del val


    #             # tensor_indeces[token] = [torch.argmax(atom[token][1][0]).item(),torch.argmax(atom[token][1][1]).item()]
    #         # else:
    #         #     tensor_indeces[token] = 0
        
    #     # for token, tensor_idx in tensor_indeces.items():
    #     #     if token not in self.lang.syntax["num_feat"]:
    #     #         atom_prediction_tensors[token] = pred[token].view(-1)[tensor_idx].reshape((1,1))
    #     #     else:
    #     #         atom_prediction_tensors[token] = [pred[token][1][0][tensor_idx[0]].view(-1).reshape((1,1)),pred[token][1][1][tensor_idx[1]].view(-1).reshape((1,1))]#.view(-1).reshape((1,1))
            
    #     # {token:pred[token].view(-1)[tensor_idx].reshape((1,1)) for token, tensor_idx in tensor_indeces.items()}
    #     del pred
    #     return atom_prediction_tensors
    
    def get_state_action_prediction_tensors_ls0(self, features, X_pd, state, atom, other_info):
        # atom = atom_pair[0]
        # origin_atom = atom_pair[1]
        # queue = list(atom.keys())
        # idx = features[-1]
        
        X, M, obs_idx, time_ptr, pid_ls, h0, p0, i, tid0, all_other_pats_ls, all_other_pats_ids_ls_ls, X_pd_ls, all_other_pats_pd_full = features
        start = time_ptr[i]
        end = time_ptr[i+1]
        i_obs = obs_idx[start:end]

        
        program, outbound_mask_ls, program_str, program_col_ls, res_all_other_pats_ls = state
        
        epsilon, id_attr, time_attr, numer_feat_ls, cat_feat_onehot_ls, delta_t, arr_idx, trainer, prev_time, current_time, obs_time, treatment_arr, outcome_arr = other_info
        
        # if arr_idx == 1 and i == 2:
        #     print()
        #  = other_info
        
        # program, outbound_mask_ls = state[0], state[1]
        
        # (X, M, obs_idx, time_ptr, pid_ls, h0, p0, i, tid0), X_pd_full, (prev_program, prev_outbound_mask_ls, prev_program_str, prev_program_col_ls, prev_all_other_pats_ls), next_atom, (program, outbound_mask_ls, program_str, program_col_ls, all_other_pats_ls)
        
        # if atom[col_id_key].max() == 116:
        #     print()
        
        # if len(program) == 0:
        #     # init_program = self.first_prog_embed.unsqueeze(0).repeat(len(X_pd),1)
        #     init_program =self.policy_net.first_prog_embed.unsqueeze(0).repeat(len(X_pd), 1)
            # pred = self.policy_net.forward_ls0(features, X_pd, [init_program], queue, 0, eval=True, replay=True, existing_atom=origin_atom)
        pred, reg_loss = self.policy_net.forward_single_time_step_single_predicate(all_other_pats_pd_full, prev_time, current_time, tid0, X, M, obs_idx, outcome_arr, i, time_ptr, treatment_arr, obs_time, delta_t, arr_idx, trainer, pid_ls, h0, p0, epsilon, id_attr, time_attr, X_pd, all_other_pats_ls, all_other_pats_ids_ls_ls, program, program_str, program_col_ls, X_pd_ls, outbound_mask_ls, res_all_other_pats_ls, numer_feat_ls, cat_feat_onehot_ls,None, None, return_reward=False, atom_sub_ls=atom, eval=True)
            # pred = self.policy_net.forward(features,X_pd, [init_program], outbound_mask_ls, atom, 0, eval=True, init=True)
            # del init_program
        # else:
        #     #program.sort()
        #     pred = self.policy_net.forward(features,X_pd, program[idx], outbound_mask_ls[idx], atom, 0, eval=True)
            # pred = self.policy_net.forward_ls(features, X_pd, state, queue, 0, eval=True, replay=True, existing_atom=origin_atom)

        # tensor_indeces = {}#{token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
        # atom_prediction_tensors = {}
        final_q_tensor_ls=[]
        for idx in range(len(atom)):
            tensor_indeces = atom[idx][pred_Q_key]#.argmax(-1)

            agg_tensor_indices = atom[idx][agg_Q_key]#.argmax(-1)
            
            atom_agg_tensors_ls = []
            for k in range(agg_tensor_indices.shape[-1]):
                atom_agg_tensors_ls.append(pred[idx][agg_Q_key][torch.arange(len(tensor_indeces)), k, agg_tensor_indices[:,k]])
            atom_agg_tensors = torch.stack(atom_agg_tensors_ls, dim=1) #atom_prediction_tensors/tensor_indeces.shape[

            
            min_time_tensor_indices = atom[idx][min_time_Q_key]#.argmax(-1)
            atom_min_time_q_tensor_ls = []
            for k in range(min_time_tensor_indices.shape[-1]):
                atom_min_time_q_tensor_ls.append(pred[idx][min_time_Q_key][torch.arange(len(tensor_indeces)), k, min_time_tensor_indices[:,k]])

            atom_min_time_q_tensor = torch.stack(atom_min_time_q_tensor_ls, dim=1) #atom_prediction_tensors/tensor_indeces.shape[

        
            # x_idx = torch.tensor(list(range(len(X_pd))))
        
            atom_prediction_tensors_ls = []
            for k in range(tensor_indeces.shape[-1]):
                atom_prediction_tensors_ls.append(pred[idx][pred_Q_key][torch.arange(len(tensor_indeces)), k, tensor_indeces[:,k]])
            atom_prediction_tensors = torch.stack(atom_prediction_tensors_ls, dim=1) #atom_prediction_tensors/tensor_indeces.shape[-1]

            # col_tensor_indices = atom[col_Q_key].argmax(-1)
            # _,col_tensor_indices = torch.topk(atom[col_Q_key], k = self.topk_act, dim=-1)
        
            # _,col_tensor_indices = torch.topk(atom[idx][col_Q_key].view(len(atom[idx][col_Q_key]),-1), k=self.topk_act, dim=-1)
            col_tensor_indices = atom[idx][col_Q_key]

            col_prediction_Q_tensor_ls = []
            
            for k in range(self.topk_act):
                col_prediction_Q_tensor_ls.append(pred[idx][col_Q_key].view(len(pred[idx][col_Q_key]), -1)[torch.arange(len(tensor_indeces)), col_tensor_indices[:,k]])
            
            col_prediction_Q_tensor = torch.stack(col_prediction_Q_tensor_ls, dim=1)
            # col_prediction_Q_tensor_ls = []
            # for k in range(col_tensor_indices.shape[-1]):
            #     col_prediction_Q_tensor_ls += pred[col_Q_key][x_idx, col_tensor_indices[:,k]]
            # col_prediction_Q_tensor = pred[col_Q_key][x_idx, col_tensor_indices]
            # col_prediction_Q_tensor = col_prediction_Q_tensor/col_tensor_indices.shape[-1]
        
            selected_num_feat_tensor_bool = atom[idx][select_num_feat_key]
        
            # if op_Q_key in atom:
            #     op_tensor_indices = atom[op_Q_key].argmax(-1)

            #     op_prediction_Q_tensor_ls = []
            #     for k in range(op_tensor_indices.shape[-1]):
            #         op_prediction_Q_tensor_ls.append(pred[op_Q_key][x_idx, k, op_tensor_indices[:,k]])
            #     op_prediction_Q_tensor = torch.stack(op_prediction_Q_tensor_ls, dim=1)
            #     op_prediction_Q_tensor = op_prediction_Q_tensor/op_tensor_indices.shape[-1]

            #     assert torch.sum(atom_prediction_tensors**selected_num_feat_tensor_bool == min_Q_val) + torch.sum(col_prediction_Q_tensor == min_Q_val) + torch.sum(op_prediction_Q_tensor == min_Q_val) == 0

            #     atom_prediction_tensors = (atom_prediction_tensors + col_prediction_Q_tensor + op_prediction_Q_tensor)/3
            # else:
            assert torch.sum(atom_prediction_tensors*selected_num_feat_tensor_bool == min_Q_val) + torch.sum(col_prediction_Q_tensor == min_Q_val) == 0# + torch.sum(op_prediction_Q_tensor < -1) == 0

            numeric_q_tensor = (atom_prediction_tensors + col_prediction_Q_tensor + atom_agg_tensors + atom_min_time_q_tensor)/4# + op_prediction_Q_tensor)/3
            
            cat_q_tensor = (col_prediction_Q_tensor + atom_agg_tensors + atom_min_time_q_tensor)/3

            final_q_tensor = numeric_q_tensor*selected_num_feat_tensor_bool + cat_q_tensor*(1-selected_num_feat_tensor_bool)

            final_q_tensor_ls.append(final_q_tensor[i_obs])
        # tensor_indeces = {}#{token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
        # for token, token_val in atom.items():
        #     if token == "num_op" or token.endswith("_prob"):
        #         continue

        #     if self.policy_net.get_prefix(token) not in self.lang.syntax["num_feat"]:
        #         # if not token.endswith("_prob"):
        #             tensor_indeces[token] = self.policy_net.grammar_token_val_to_num[token][token_val]
        #     else:
        #         # tensor_indeces[token] = [torch.argmax(atom[token][1][0]).item(),torch.argmax(atom[token][1][1]).item()]
        #         tensor_indeces[token] = torch.argmax(atom[token][1]).item()
        #     # else:
        #     #     tensor_indeces[token] = 0
        # atom_prediction_tensors = {}
        # for token, tensor_idx in tensor_indeces.items():
        #     if self.policy_net.get_prefix(token) not in self.lang.syntax["num_feat"]:
        #         atom_prediction_tensors[token] = pred[token].view(-1)[tensor_idx].reshape((1,1))
        #     else:
        #         if token.endswith("_ub"):
        #             atom_prediction_tensors[self.policy_net.get_prefix(token)] = pred[token][1][tensor_idx].view(-1)
                # atom_prediction_tensors[token] = [pred[token][1][0][tensor_idx[0]].view(-1).reshape((1,1)),pred[token][1][1][tensor_idx[1]].view(-1).reshape((1,1))]#.view(-1).reshape((1,1))

        # for token, token_val in atom.items():
        #     # if token == "num_op" or token.endswith("_prob"):
        #     #     continue

        #     # if token not in self.lang.syntax["num_feat"]:
        #     if not type(token) is tuple:
        #         # if not token.endswith("_prob"):
        #             # tensor_indeces[token] = self.policy_net.grammar_token_val_to_num[token][token_val]
        #             if not type(token_val) is dict:
        #                 tensor_idx = self.policy_net.grammar_token_val_to_num[token][token_val]
        #                 val = pred[token][:,tensor_idx].reshape((len(X_pd),1))
        #                 atom_prediction_tensors[token] = val
        #                 del val
        #             else:
        #                 for token_val_key in token_val:
        #                     token_val_sample_ids = token_val[token_val_key]
        #                     tensor_idx = self.policy_net.grammar_token_val_to_num[token][token_val_key]
        #                     val = pred[token][token_val_sample_ids,tensor_idx]
        #                     atom_prediction_tensors[token][token_val_sample_ids] = val
        #                     del val
                        
        #     else:
        #         if not "pred_score" in atom_prediction_tensors:
        #         pred_val = pred[token]
        #         for token_key in token:
                    
        #             # token_key = token_key[0]
        #             # lb_probs = pred_val[1][token_key][0]
        #             probs = pred_val[1][token_key]
        #             sample_ids = token_val[2][token_key].view(-1)
        #             sample_cln_id_ls = token_val[3][token_key]
        #             val = probs[sample_ids.view(-1), sample_cln_id_ls.view(-1)]
        #             if token_key.endswith("_lb"):
        #                 atom_prediction_tensors["pred_score"][0][sample_ids] = val
        #             elif token_key.endswith("_ub"):
        #                 atom_prediction_tensors["pred_score"][1][sample_ids] = val
        #             del val
        #             # val = ub_probs[sample_ids.view(-1), sample_cln_id_ls[1].view(-1)]
        #             # atom_prediction_tensors[token][1][sample_ids] = val
        #             # del val


        #         # tensor_indeces[token] = [torch.argmax(atom[token][1][0]).item(),torch.argmax(atom[token][1][1]).item()]
        #     # else:
        #     #     tensor_indeces[token] = 0
        
        # # for token, tensor_idx in tensor_indeces.items():
        # #     if token not in self.lang.syntax["num_feat"]:
        # #         atom_prediction_tensors[token] = pred[token].view(-1)[tensor_idx].reshape((1,1))
        # #     else:
        # #         atom_prediction_tensors[token] = [pred[token][1][0][tensor_idx[0]].view(-1).reshape((1,1)),pred[token][1][1][tensor_idx[1]].view(-1).reshape((1,1))]#.view(-1).reshape((1,1))
            
        # # {token:pred[token].view(-1)[tensor_idx].reshape((1,1)) for token, tensor_idx in tensor_indeces.items()}
        # del pred
        return torch.mean(torch.stack(final_q_tensor_ls,dim=1), dim=-1), reg_loss
    
    def get_state_action_prediction_tensors_ls0_medical(self, features, X_pd, state, atom):
        # atom = atom_pair[0]
        # origin_atom = atom_pair[1]
        queue = list(atom.keys())
        
        program = state
        
        if len(program) == 0:
            # init_program = self.first_prog_embed.unsqueeze(0).repeat(len(X_pd),1)
            init_program =self.first_prog_embed.unsqueeze(0).repeat(len(X_pd), 1)
            # pred = self.policy_net.forward_ls0(features, X_pd, [init_program], queue, 0, eval=True, replay=True, existing_atom=origin_atom)
            pred = self.policy_net.forward_ls0(features,X_pd, [init_program], atom, 0, eval=True, init=True)
            del init_program
        else:
            #program.sort()
            pred = self.policy_net.forward_ls0(features,X_pd, program, atom, 0, eval=True)
            # pred = self.policy_net.forward_ls(features, X_pd, state, queue, 0, eval=True, replay=True, existing_atom=origin_atom)

        # tensor_indeces = {}#{token:self.policy_net.grammar_token_val_to_num[token][token_val] for token, token_val in atom.items()}
        # atom_prediction_tensors = {}
        # tensor_indeces = atom[pred_Q_key].argmax(-1)
        
        x_idx = torch.tensor(list(range(len(X_pd))))
        
        # atom_prediction_tensors_ls = []
        # for k in range(tensor_indeces.shape[-1]):
        #     atom_prediction_tensors_ls.append(pred[pred_Q_key][x_idx, k, tensor_indeces[:,k]])
        # atom_prediction_tensors = torch.stack(atom_prediction_tensors_ls, dim=1) #atom_prediction_tensors/tensor_indeces.shape[-1]

        # col_tensor_indices = atom[col_Q_key].argmax(-1)
        # _,col_tensor_indices = torch.topk(atom[col_Q_key], k = self.topk_act, dim=-1)
        
        _,col_tensor_indices = torch.topk(atom[col_Q_key].view(len(atom[col_Q_key]),-1), k=self.topk_act, dim=-1)


        col_prediction_Q_tensor_ls = []
        
        for k in range(self.topk_act):
            col_prediction_Q_tensor_ls.append(pred[col_Q_key].view(len(pred[col_Q_key]), -1)[x_idx, col_tensor_indices[:,k]])
        
        col_prediction_Q_tensor = torch.stack(col_prediction_Q_tensor_ls, dim=1)
        # col_prediction_Q_tensor_ls = []
        # for k in range(col_tensor_indices.shape[-1]):
        #     col_prediction_Q_tensor_ls += pred[col_Q_key][x_idx, col_tensor_indices[:,k]]
        # col_prediction_Q_tensor = pred[col_Q_key][x_idx, col_tensor_indices]
        # col_prediction_Q_tensor = col_prediction_Q_tensor/col_tensor_indices.shape[-1]
        
        # if op_Q_key in atom:
        #     op_tensor_indices = atom[op_Q_key].argmax(-1)

        #     op_prediction_Q_tensor_ls = []
        #     for k in range(op_tensor_indices.shape[-1]):
        #         op_prediction_Q_tensor_ls.append(pred[op_Q_key][x_idx, k, op_tensor_indices[:,k]])
        #     op_prediction_Q_tensor = torch.stack(op_prediction_Q_tensor_ls, dim=1)
        #     op_prediction_Q_tensor = op_prediction_Q_tensor/op_tensor_indices.shape[-1]

        #     assert torch.sum(atom_prediction_tensors == min_Q_val) + torch.sum(col_prediction_Q_tensor == min_Q_val) + torch.sum(op_prediction_Q_tensor == min_Q_val) == 0

        #     atom_prediction_tensors = (atom_prediction_tensors + col_prediction_Q_tensor + op_prediction_Q_tensor)/3
        # else:
        #     assert torch.sum(atom_prediction_tensors == min_Q_val) + torch.sum(col_prediction_Q_tensor == min_Q_val) == 0# + torch.sum(op_prediction_Q_tensor < -1) == 0

        #     atom_prediction_tensors = (atom_prediction_tensors + col_prediction_Q_tensor)/2# + op_prediction_Q_tensor)/3


        return col_prediction_Q_tensor
    
    
    #takes an atom, and the maximal tensors used to produce it, and returns a Q value
    def get_atom_Q_value(self, atom:dict, atom_prediction_tensors: dict):
        formula = atom_prediction_tensors["formula"]
        if atom["formula"] == "end":
            one = torch.tensor([[1]], dtype=torch.float,device=self.device)
            feat, op, constant = one, one, one
        else:
            if "num_feat" in atom:
                feat_name = atom["num_feat"]
                feat = atom_prediction_tensors["num_feat"]
                op = 1#atom_prediction_tensors["num_op"]
            else:
                feat_name = atom["cat_feat"]
                feat = atom_prediction_tensors["cat_feat"]
                op = 1#atom_prediction_tensors["cat_op"]
            constant = atom_prediction_tensors[feat_name]
        # Q = formula*feat*op*constant[0]*constant[1]
        Q = constant
        return Q[0]
    
    def get_atom_Q_value2(self, atom:dict, atom_prediction_tensors: dict):
        formula = atom_prediction_tensors["formula"]
        if atom["formula"] == "end":
            one = torch.tensor([[1]], dtype=torch.float,device=self.device)
            feat, op, constant = one, one, one
        else:
            if "num_feat" in atom:
                feat_name = atom["num_feat"]
                feat = atom_prediction_tensors["num_feat"]
                op = 1#atom_prediction_tensors["num_op"]
            else:
                feat_name = atom["cat_feat"]
                feat = atom_prediction_tensors["cat_feat"]
                op = 1#atom_prediction_tensors["cat_op"]
            constant = atom_prediction_tensors[feat_name]
        # Q = formula*feat*op*constant[0]*constant[1]
        # Q = constant[0]*constant[1]
        # return Q[0]
        return torch.cat([constant[0].view(-1), constant[1].view(-1)])

    def get_atom_Q_value_ls(self, atom:dict, atom_prediction_tensors: dict):
        op=1
        formula = atom_prediction_tensors["formula"]
        if atom["formula"] == "end":
            one = torch.FloatTensor([[1]])
            feat, op, constant = one, one, one
        else:
            if "num_feat" in atom:
                feat_name = atom["num_feat"]
                feat = atom_prediction_tensors["num_feat"]
                # op = atom_prediction_tensors["num_op"]
            else:
                feat_name = atom["cat_feat"]
                feat = atom_prediction_tensors["cat_feat"]
                # op = atom_prediction_tensors["cat_op"]
            # constant = atom_prediction_tensors[tuple([tuple([item]) for item in list(feat_name.keys())])]
            constant = atom_prediction_tensors["pred_score"]
        # Q = formula.view(-1)*feat.view(-1)*op*
        # Q = constant[0].view(-1)*
        Q = constant[1].view(-1)
        return Q
    
    def observe_transition(self, transition: Transition):
        self.memory.push(transition)

 
    def optimize_model(self):
        if len(self.memory) < self.batch_size: return 0.0

        # Pull out a batch and its relevant features
        batch = self.memory.sample(self.batch_size)
        non_final_mask = torch.tensor([transition.next_program is not None for transition in batch], dtype=torch.bool, device=self.device)
        non_final_samples = [transition for transition in batch if transition.next_program is not None]
        state_action_batch = [(transition.features, transition.data, transition.program, transition.action) for transition in batch]
        reward_batch = torch.tensor([[transition.reward] for transition in batch], device=self.device, requires_grad=True, dtype=torch.float)

        #get Q value for (s,a)
        state_action_pred = [(a[0],self.get_state_action_prediction_tensors(f,d, p,a)) for f,d, p,a in state_action_batch]
        state_action_values = torch.stack([self.get_atom_Q_value(a,t) for a,t in state_action_pred])

        #get Q value for (s', max_a')
        next_state_pred_non_final = [self.predict_next_state_with_tensor_info(sample.features, sample.data, sample.next_program) for sample in non_final_samples]
        next_state_values = torch.zeros([self.batch_size, 1], device=self.device, dtype=torch.float)
        if len(next_state_pred_non_final) > 0:
            next_state_values_non_final = torch.stack([self.get_atom_Q_value(atom, max_tensors) for atom, max_tensors in next_state_pred_non_final])
            next_state_values[non_final_mask] = next_state_values_non_final

        # Prepare the loss function
        expected_state_action_values = (next_state_values * self.gamma) + reward_batch
        # Compute the loss
        loss = self.criterion(state_action_values.view(-1), expected_state_action_values.view(-1))
        self.optimizer.zero_grad()
        loss.backward(retain_graph=True)
        torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 1)
        self.optimizer.step()
        # for i in range(len(batch)):
        #     print(batch[i].data)
        #     print("program::")
        #     for pid in range(len(batch[i].program)):
        #         print(batch[i].program[pid])
        # print("loss::", loss)
        # print("expected_state_action_values::", expected_state_action_values)
        # print("next_state_values::", next_state_values)
        # print("reward_batch::", reward_batch)
        # print("state_action_values::", state_action_values)

        # Return loss
        return loss.detach()
    
    def optimize_model2(self):
        if len(self.memory) < self.batch_size: return 0.0

        # Pull out a batch and its relevant features
        batch = self.memory.sample(self.batch_size)
        non_final_mask = torch.tensor([transition.next_program is not None for transition in batch], dtype=torch.bool, device=self.device)
        non_final_samples = [transition for transition in batch if transition.next_program is not None]
        state_action_batch = [(transition.features, transition.data, transition.program, transition.action) for transition in batch]
        reward_batch = torch.tensor([transition.reward for transition in batch], device=self.device, requires_grad=True, dtype=torch.float)

        #get Q value for (s,a)
        state_action_pred = [(a,self.get_state_action_prediction_tensors(f,d, p,a)) for f,d, p,a in state_action_batch]
        state_action_values = torch.stack([self.get_atom_Q_value2(a,t) for a,t in state_action_pred])

        #get Q value for (s', max_a')
        next_state_pred_non_final = [self.predict_next_state_with_tensor_info(sample.features, sample.data, sample.next_program) for sample in non_final_samples]
        next_state_values = torch.zeros([self.batch_size, 2], device=self.device, dtype=torch.float)
        if len(next_state_pred_non_final) > 0:
            next_state_values_non_final = torch.stack([self.get_atom_Q_value2(atom, max_tensors) for atom, max_tensors in next_state_pred_non_final])
            next_state_values[non_final_mask] = next_state_values_non_final

        # Prepare the loss function
        expected_state_action_values = (next_state_values * self.gamma) + reward_batch
        # Compute the loss
        loss = self.criterion(state_action_values[:,1:2].repeat(1,2), expected_state_action_values)
        self.optimizer.zero_grad()
        loss.backward(retain_graph=True)
        torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 1)
        self.optimizer.step()

        return loss.detach()
    
    # def optimize_model_ls(self):
    #     if len(self.memory) < self.mem_sample_size: return 0.0

    #     # Pull out a batch and its relevant features
    #     batch = self.memory.sample(self.mem_sample_size)
    #     non_final_samples = [transition for transition in batch if transition.next_program is not None]
    #     state_action_batch = [(transition.features, transition.data, transition.program, transition.action) for transition in batch]

    #     #get Q value for (s,a)
    #     state_action_pred = [(a,self.get_state_action_prediction_tensors_ls(f,d, p,a)) for f,d, p,a in state_action_batch]
    #     state_action_values = torch.stack([self.get_atom_Q_value_ls(a,t) for a,t in state_action_pred])
        
    #     #get Q value for (s', max_a')
    #     next_state_pred_non_final = [self.predict_next_state_with_tensor_info_ls(sample.features, sample.data, sample.next_program) for sample in non_final_samples]
    #     if len(next_state_pred_non_final) > 0:
    #         next_state_values_non_final = torch.stack([self.get_atom_Q_value_ls(atom, max_tensors) for atom, max_tensors in next_state_pred_non_final])
    #         next_state_values[non_final_mask] = next_state_values_non_final
    #         del next_state_values_non_final
    #     # Prepare the loss function
    #     expected_state_action_values = (next_state_values * self.gamma) + reward_batch
    #     # Compute the loss
    #     loss = self.criterion(state_action_values.view(-1), expected_state_action_values.view(-1))
    #     self.optimizer.zero_grad()
    #     loss.backward(retain_graph=True)
    #     # torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 1)
    #     self.optimizer.step()
        
    #     # for item in non_final_samples:
    #     #     del item
    #     # for  item in state_action_batch:
    #     #     del item
    #     # for item in state_action_pred:
    #     #     del item
    #     # for item in next_state_pred_non_final:
    #     #     del item
    #     # non_final_samples.clear()
    #     # state_action_pred.clear()
    #     # state_action_batch.clear()
    #     # non_final_samples.clear()
    #     # del state_action_values, expected_state_action_values, next_state_values, reward_batch, state_action_pred, next_state_pred_non_final, non_final_mask
    #     # del non_final_samples, batch, state_action_batch
    #     # for i in range(len(batch)):
    #     #     print(batch[i].data)
    #     #     print("program::")
    #     #     for pid in range(len(batch[i].program)):
    #     #         print(batch[i].program[pid])
    #     # print(batch[0].data)
    #     # print(batch[1].data)
    #     # print("loss::", loss)
    #     # print("expected_state_action_values::", expected_state_action_values)
    #     # print("next_state_values::", next_state_values)
    #     # print("reward_batch::", reward_batch)
    #     # print("state_action_values::", state_action_values)
    #     # Return loss
    #     return_loss = loss.detach()
    #     del loss
    #     return return_loss
    
    def optimize_model_ls0(self):
        if len(self.memory) < self.mem_sample_size: return torch.tensor(0.0)

        # Pull out a batch and its relevant features
        batch = self.memory.sample(self.mem_sample_size)
        non_final_mask = torch.tensor([transition.next_program is not None for transition in batch], dtype=torch.bool, device=self.device)
        non_final_samples = [transition for transition in batch if transition.next_program is not None]
        state_action_batch = [(transition.features, transition.data, transition.program, transition.action, transition.other_info) for transition in batch]
        if not self.weighted_reward:
            reward_batch = torch.cat([transition.reward.mean(-1) for transition in batch]).to(self.device)
        else:
            r_weight = torch.tensor([1,5,1], dtype=torch.float).to(self.device)
            reward_batch = torch.cat([transition.reward@r_weight/r_weight.sum() for transition in batch]).to(self.device)

        #get Q value for (s,a)
        # if not self.do_medical:
        state_action_pred = [(a,self.get_state_action_prediction_tensors_ls0(f,d, p,a, o)) for f,d, p,a, o in state_action_batch]
        # else:
        #     state_action_pred = [(a,self.get_state_action_prediction_tensors_ls0_medical(f,d, p,a)) for f,d, p,a in state_action_batch]
        # state_action_values = torch.stack([self.get_atom_Q_value_ls(a,t) for a,t in state_action_pred])
        state_action_values_ls =  [t[0] for a,t in state_action_pred]
        state_action_values = torch.cat(state_action_values_ls)
        state_action_values = state_action_values.to(self.device)
        
        reg_loss = 0#torch.mean(torch.cat([t[1].view(-1) for a,t in state_action_pred]))
        
        #get Q value for (s', max_a')
        # if not self.do_medical:
        next_state_pred_non_final = [self.predict_next_state_with_tensor_info_ls0(sample.features, sample.data, sample.next_program, sample.other_info) for sample in non_final_samples]
        # next_state_values_non_final = torch.cat(next_state_pred_non_final)
        # else:
        #     next_state_pred_non_final = [self.predict_next_state_with_tensor_info_ls0_medical(sample.features, sample.data, sample.next_program) for sample in non_final_samples]
        # next_state_values = torch.zeros([self.mem_sample_size, self.batch_size], dtype=torch.float, device=self.device)
        # if len(next_state_pred_non_final) > 0:
        #     # next_state_values_non_final = torch.stack([self.get_atom_Q_value_ls(atom, max_tensors) for atom, max_tensors in next_state_pred_non_final])
        #     next_state_values_non_final = torch.cat(next_state_pred_non_final)
        #     next_state_values[non_final_mask] = next_state_values_non_final
            # del next_state_values_non_final
        next_state_values = torch.zeros_like(state_action_values)# next_state_values_non_final.to(self.device)
        # Prepare the loss function
        idx1 = 0
        idx2 = 0
        start_idx = 0
        for b in non_final_mask:
            if b:
                next_state_values[start_idx:start_idx+state_action_values_ls[idx2].shape[0]] = next_state_pred_non_final[idx1]
                idx1 += 1
            if not b:
                print()
            start_idx += state_action_values_ls[idx2].shape[0]
            idx2 += 1
            
        
        expected_state_action_values = (next_state_values * self.gamma) + reward_batch.view(next_state_values.shape)
        # Compute the loss
        loss = self.criterion(state_action_values.view(-1), expected_state_action_values.view(-1)) + self.policy_net.mixing*reg_loss
        self.optimizer.zero_grad()
        loss.backward(retain_graph=True)
        # torch.nn.utils.clip_grad_value_(self.policy_net.parameters(), 1)
        self.optimizer.step()
        
        return_loss = loss.detach()
        del loss
        return return_loss

    def update_target(self):
        self.target_net.load_state_dict(self.policy_net.state_dict())

