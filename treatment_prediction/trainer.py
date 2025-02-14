import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import GRU_ODE.data_utils as data_utils
from rl_algorithm import DQN_all_temporal
import logging
import pandas as pd
import numpy as np
import operator
from mortalty_prediction.rl_models.enc_dec import col_id_key, col_key, pred_Q_key, pred_v_key, col_Q_key, prev_prog_key, op_key, Transition, outbound_key
from mortalty_prediction.full_experiments.create_language import *
from tqdm import tqdm
import torch
from mortalty_prediction.utils_mortality.metrics import metrics_maps
from sklearn.metrics import recall_score, f1_score, roc_auc_score
from torch.utils.data import DataLoader
from mortalty_prediction.datasets.EHR_datasets import *
from mortalty_prediction.rl_models.enc_dec_medical import range_key
from mortalty_prediction.full_experiments.cluster_programs import *
import gc


class Trainer_all_temporal:
    # lang=lang, train_dataset=train_dataset, valid_dataset=valid_dataset,test_dataset = test_dataset, train_feat_embeddings=train_feat_embeddings, valid_feat_embeddings=valid_feat_embeddings, test_feat_embeddings=test_feat_embeddings, program_max_len=program_max_len, topk_act=args.topk_act,   learning_rate=args.learning_rate, batch_size=args.batch_size, epochs=args.epochs,       is_log = args.is_log, dropout_p=args.dropout_p, feat_range_mappings=feat_range_mappings, seed=args.seed, work_dir=work_dir, numeric_count=numeric_count, category_count=category_count , model=args.model, rl_algorithm=args.rl_algorithm,model_config = model_config,rl_config = rl_config
    def __init__(self, lang:Language, train_dataset, valid_dataset, test_dataset, train_feat_embeddings, valid_feat_embeddings, test_feat_embeddings, program_max_len, topk_act, learning_rate, batch_size, epochs, numer_feat_ls, cat_feat_ls, cat_feat_ls_onehot, feat_to_onehot_embedding, unique_treatment_label_ls, device, is_log, dropout_p, feat_range_mappings, seed, work_dir, numeric_count=None, category_count=None, category_sum_count=None, model="mlp", rl_algorithm= "dqn", model_config=None, rl_config=None, feat_group_names=None, removed_feat_ls=None, prefer_smaller_range = False, prefer_smaller_range_coeff = 0.5, method_two=False, args = None):
        self.topk_act =topk_act
        self.numer_feat_ls = numer_feat_ls
        self.cat_feat_ls=cat_feat_ls
        self.cat_feat_ls_onehot = cat_feat_ls_onehot
        self.feat_to_onehot_embedding = feat_to_onehot_embedding
        self.device = device
        # if rl_algorithm == "dqn":
        self.dqn = DQN_all_temporal(device,unique_treatment_label_ls, lang=lang, replay_memory_capacity=rl_config["replay_memory_capacity"], learning_rate=learning_rate, batch_size=batch_size, gamma=rl_config["gamma"], program_max_len=program_max_len, dropout_p=dropout_p, feat_range_mappings=feat_range_mappings, mem_sample_size=rl_config["mem_sample_size"], seed=seed, numeric_count=numeric_count, category_count=category_count,category_sum_count = category_sum_count, has_embeddings=(train_feat_embeddings is not None), model=model, topk_act=topk_act, model_config = model_config, rl_config=rl_config, feat_group_names = feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, method_two=method_two, args = args, work_dir = work_dir)
        # self.dqn = DQN_all_temporal(lang=lang, replay_memory_capacity=rl_config["replay_memory_capacity"], learning_rate=learning_rate, batch_size=batch_size, gamma=rl_config["gamma"], program_max_len=program_max_len, dropout_p=dropout_p, feat_range_mappings=feat_range_mappings, mem_sample_size=rl_config["mem_sample_size"], seed=seed, numeric_count=numeric_count, category_count=category_count,category_sum_count = category_sum_count, has_embeddings=(train_feat_embeddings is not None), model=model, topk_act=topk_act, model_config = model_config, feat_group_names = feat_group_names, removed_feat_ls=removed_feat_ls, prefer_smaller_range = prefer_smaller_range, prefer_smaller_range_coeff = prefer_smaller_range_coeff, method_two=method_two, args = args)
        self.epsilon = rl_config["epsilon"]
        self.epsilon_falloff = rl_config["epsilon_falloff"]
        self.target_update = rl_config["target_update"]

        self.rl_algorithm = rl_algorithm
        self.feat_range_mappings = feat_range_mappings
        
        self.work_dir = work_dir
        
        self.epochs = epochs
        self.train_dataset = train_dataset
        self.valid_dataset = valid_dataset
        self.test_dataset = test_dataset
        self.lang = lang
        
        self.program_max_len = program_max_len
        self.is_log = is_log
        self.batch_size = batch_size
        self.train_feat_embeddings=train_feat_embeddings
        self.valid_feat_embeddings=valid_feat_embeddings
        self.test_feat_embeddings=test_feat_embeddings
        self.do_medical = args.do_medical
        self.multilabel = (args.dataset_name == four)
        # self.do_medical = do_medical
        if self.is_log:
            self.logger = logging.getLogger()


    def get_test_decision_from_db(self, data: pd.DataFrame):
        if data.shape[0] == 0:
            return -1
        return data['label'].value_counts().idxmax()
    
    def get_test_decision_from_db_ls(self, data_ls: pd.DataFrame):
        if len(data_ls) == 0:
            return -1
        
        label_ls = []
        prob_label_ls = []
        for data in data_ls:
            if len(data) == 0:
                label_ls.append(-1)
                prob_label_ls.append(-1)
                continue
            label = data['label'].value_counts().idxmax()
            prob_label = np.mean(data['label'])
            label_ls.append(label)
            prob_label_ls.append(prob_label)
        return label_ls, prob_label_ls
    
    def get_test_decision_from_db_ls_multi(self, data_ls):
        if len(data_ls) == 0:
            return -1
        
        label_ls = []
        prob_label_ls = []
        for sub_data_ls in data_ls:
            sub_label_ls = []
            sub_prob_label_ls = []
            for data in sub_data_ls:
                if len(data) == 0:
                    # sub_label_ls.append(-1)
                    # sub_prob_label_ls.append(-1)
                    continue
                label = data['label'].value_counts().idxmax()
                if self.multilabel:
                    prob_label = np.mean(np.array(list(data['label'])), axis=0)
                else:
                    prob_label = np.mean(data['label'])
                sub_label_ls.append(label)
                sub_prob_label_ls.append(prob_label)
            if self.multilabel:
                if len(sub_label_ls) <= 0:
                    label_ls.append(np.array([-1]*len(self.train_dataset.data["label"][0])))
                    prob_label_ls.append(np.array([-1]*len(self.train_dataset.data["label"][0])))
                else:
                    prob_label = np.mean(np.stack(sub_prob_label_ls), axis=0)
                    prob_label_ls.append(prob_label)
                    label_ls.append((prob_label > 0.5).astype(np.int32))
            else:
                if len(sub_label_ls) <= 0:    
                    label_ls.append(-1)
                    prob_label_ls.append(-1)
                else:
                    
                    prob_label = np.mean(np.array(sub_prob_label_ls))
                    prob_label_ls.append(prob_label)
                    
                    if prob_label == 0.5:
                        label_ls.append(-1)
                    elif prob_label > 0.5:
                        label_ls.append(1)
                    else:
                        label_ls.append(0)
                
            
        return label_ls, prob_label_ls

    def check_db_constrants(self, data: pd.DataFrame,  y: int) -> float:
        if len(data) == 0:
            return 0
        same = data.loc[data['label'] == y]["PAT_ID"].nunique()
        total = data['PAT_ID'].nunique()
        return same / total

    def check_db_constrants_ls(self, data_ls,  y_ls):
        # if len(data) == 0:
        #     return 0
        rwd_ls = []
        for idx in range(len(data_ls)):
            sub_data_ls = data_ls[idx]
            sub_rwd_ls = []
            for data in sub_data_ls:
                # if y_ls[idx].numel() == 1:
                if not self.multilabel:
                    y = int(y_ls[idx].item())
                    # same = data.loc[data['label'] == y]["PAT_ID"].nunique()
                    # total = data['PAT_ID'].nunique()
                    if len(data) == 0:
                        sub_rwd_ls.append(0)
                    else:
                        sub_rwd_ls.append(np.mean(data['label'] == y))
                else:
                    y = y_ls[idx]
                    score_ls = []
                    total = data['PAT_ID'].nunique()
                    if total == 0:
                        sub_rwd_ls.append([0]*y_ls[idx].numel())
                    else:
                        for cid in range(y_ls[idx].numel()):
                            curr_same = data.loc[np.array(list(data['label']))[:,cid] == y[cid].item()]["PAT_ID"].nunique()
                            curr_score = curr_same/total
                            score_ls.append(curr_score)
                        # score = score/y_ls[idx].numel()
                        sub_rwd_ls.append(score_ls)


                
            
            rwd_ls.append(sub_rwd_ls) 
            # if total == 0:
            #     rwd_ls.append(0)
            # else:
            #     rwd_ls.append(same / total) 
        return np.array(rwd_ls)

    def check_x_constraint(self, X: pd.DataFrame, atom: dict, lang) -> bool:
        return lang.evaluate_atom_on_sample(atom, X)

    def check_program_constraint(self, prog: list) -> bool:
        return len(prog) < self.program_max_len
    
    def identify_op(self, X:pd, atom:dict):

        atom_ls = []
        

        atom1 = dict()
        for k in atom:
            if k not in self.lang.syntax["num_feat"]:
                atom1[k] = atom[k]
            else:
                atom1[k] = atom[k][0][0]
                atom1[k + "_prob"] = atom[k][1][0]

        atom1["num_op"] = operator.__ge__

        atom2 = dict()
        for k in atom:
            if k not in self.lang.syntax["num_feat"]:
                atom2[k] = atom[k]
            else:
                atom2[k] = atom[k][0][1]
                atom2[k + "_prob"] = atom[k][1][1]
        atom2["num_op"] = operator.__le__
        atom_ls.append(atom1)
        atom_ls.append(atom2)
            
        return atom_ls
    
    def identify_op_ls(self, batch_size:int, atom:dict):

        atom_ls = []        

        # atom1 = [dict()]*batch_size
        atom1 = []

        atom2 = []
        for _ in range(batch_size):
            atom2.append(dict())
        for _ in range(batch_size):
            atom1.append(dict())
        for k in atom:
            # if k not in self.lang.syntax["num_feat"]:
            if type(k) is not tuple:
                if type(atom[k]) is not dict:
                    for atom_id in range(batch_size):
                        atom1[atom_id][k] = atom[k]
                        atom2[atom_id][k] = atom[k]
                else:
                    # atom1[k] = [None]*batch_size
                    for selected_item in atom[k]:
                        sample_ids = atom[k][selected_item]
                        for sample_id in sample_ids:
                            atom1[sample_id.item()][k] = selected_item
                            atom2[sample_id.item()][k] = selected_item
            else:
                
                # atom1[k] = [None]*batch_size
                # atom1[k + "_prob"] = [None]*batch_size
                if k[0].endswith("_lb"):
                    for selected_item in atom[k][2]:
                        sample_ids = atom[k][2][selected_item]
                        for sample_id_id in range(len(sample_ids)):
                            atom1[sample_ids[sample_id_id].item()][self.dqn.policy_net.get_prefix(selected_item)] = atom[k][0][selected_item][sample_id_id]
                            # atom1[sample_ids[sample_id_id].item()][selected_item + "_prob"] = atom[k][1][selected_item][0][sample_id_id]
                else:
                    for selected_item in atom[k][2]:
                        sample_ids = atom[k][2][selected_item]
                        for sample_id_id in range(len(sample_ids)):
                            atom2[sample_ids[sample_id_id].item()][self.dqn.policy_net.get_prefix(selected_item)] = atom[k][0][selected_item][sample_id_id]
                            # atom2[sample_ids[sample_id_id].item()][selected_item + "_prob"] = atom[k][1][selected_item][0][sample_id_id]
                        # atom1[sample_ids[sample_id_id].item()][k + "_"] = atom[k][1][selected_item][0][sample_id_id.item()]


                # atom1[k] = atom[k][0][0]
                # atom1[k + "_prob"] = atom[k][1][0]
                # atom1[k + "_sample_ids"] = atom[k][2][0]
        for sample_id in range(len(atom1)):
            atom1[sample_id]["num_op"] = operator.__ge__   

        for sample_id in range(len(atom2)):
            atom2[sample_id]["num_op"] = operator.__le__   

        
        # for k in atom:
        #     # if k not in self.lang.syntax["num_feat"]:
        #     if type(k) is not tuple:
        #         if type(atom[k]) is not dict:
        #             for atom_id in range(batch_size):
        #                 atom2[atom_id][k] = atom[k]
        #         else:
        #             for selected_item in atom[k]:
        #                 sample_ids = atom[k][selected_item]
        #                 for sample_id in sample_ids:
        #                     atom2[sample_id.item()][k] = selected_item
        #     else:
                
        #         for selected_item in atom[k][2]:
        #             sample_ids = atom[k][2][selected_item]
        #             for sample_id_id in range(len(sample_ids)):
        #                 atom2[sample_ids[sample_id_id].item()][selected_item] = atom[k][0][1][selected_item][sample_id_id]
        #                 atom2[sample_ids[sample_id_id].item()][selected_item + "_prob"] = atom[k][1][selected_item][1][sample_id_id]
        #                 # atom1[sample_ids[sample_id_id].item()][k + "_"] = atom[k][1][selected_item][0][sample_id_id.item()]


        #         # atom1[k] = atom[k][0][0]
        #         # atom1[k + "_prob"] = atom[k][1][0]
        #         # atom1[k + "_sample_ids"] = atom[k][2][0]
        # for sample_id in range(len(atom2)):
        #     atom2[sample_id]["num_op"] = operator.__le__  


        # atom2 = dict()
        # for k in atom:
        #     if k not in self.lang.syntax["num_feat"]:
        #         atom2[k] = atom[k]
        #     else:
        #         atom2[k] = atom[k][0][1]
        #         atom2[k + "_prob"] = atom[k][1][1]
        # atom2["num_op"] = operator.__le__
        atom_ls.append(atom1)
        atom_ls.append(atom2)
            
        return atom_ls
    def check_x_constraint_with_atom_ls(self, X: pd.DataFrame, atom_ls:list, lang) -> bool:
        satisfy_bool=True
        for atom in atom_ls:
            curr_bool = lang.evaluate_atom_on_sample(atom, X)
            satisfy_bool = satisfy_bool & curr_bool
        return satisfy_bool

    # def train_epoch(self, epoch, train_loader):
    #     success, failure, sum_loss = 0, 0, 0.
    #     # iterator = tqdm(enumerate(self.train_dataset), desc="Training Synthesizer", total=len(self.train_dataset))
    #     # for episode_i, val in iterator:
    #     iterator = tqdm(enumerate(train_loader), desc="Training Synthesizer", total=len(train_loader))
        
    #     # pos_count = np.sum(self.train_dataset.data["label"] == 1)
    #     # neg_count = np.sum(self.train_dataset.data["label"] == 0)
    #     # sample_weights = torch.ones(len(self.train_dataset.data))
    #     # sample_weights[np.array(self.train_dataset.data["label"]) == 1] = neg_count/(neg_count + pos_count)
    #     # sample_weights[np.array(self.train_dataset.data["label"]) == 0] = pos_count/(neg_count + pos_count)
    #     # train_sampler = torch.utils.data.sampler.WeightedRandomSampler(sample_weights, len(self.train_dataset.data), replacement=True)
    #     # iterator = torch.utils.data.DataLoader(self.train_dataset, batch_size=1, collate_fn = EHRDataset.collate_fn)
    #     # episode_i = 0
    #     # for val in iterator:
    #     # all_rand_ids = torch.randperm(len(self.train_dataset))
    #     # for episode_i, sample_idx in iterator:
    #     for episode_i, val in iterator:
    #         (all_other_pats_ls, X_pd_ls, X), y = val
    #         # (all_other_pats, X_pd, X), y = self.train_dataset[all_rand_ids[sample_idx].item()]
    #         program = []
    #         program_str = [[] for _ in range(len(X_pd_ls))]
    #         program_atom_ls = [[] for _ in range(len(X_pd_ls))]
            
            
    #         while True: # episode
    #             atom,origin_atom = self.dqn.predict_atom_ls(features=X, X_pd_ls=X_pd_ls, program=program, epsilon=self.epsilon)
    #             atom_ls_ls = self.identify_op_ls(X.shape[0], atom)
    #             reorg_atom_ls_ls= [[] for _ in range(len(X_pd_ls))]

    #             next_program = program.copy()
    #             next_program_str = program_str.copy()
    #             for new_atom_ls in atom_ls_ls:

    #                 curr_vec_ls = self.dqn.atom_to_vector_ls(new_atom_ls)

    #                 next_program.append(torch.stack(curr_vec_ls))

    #                 curr_atom_str_ls = self.lang.atom_to_str_ls(new_atom_ls)

    #                 for vec_idx in range(len(curr_vec_ls)):
    #                     vec = curr_vec_ls[vec_idx]
    #                     atom_str = curr_atom_str_ls[vec_idx]
                        
    #                     next_program_str[vec_idx].append(atom_str)
    #                     program_atom_ls[vec_idx].append(new_atom_ls[vec_idx])
    #                     reorg_atom_ls_ls[vec_idx].append(new_atom_ls[vec_idx])
    #                 # atom["num_op"] = atom_op
                    
                    
    #                 # next_program_str = next_program_str + []
                    
    #                 # program_atom_ls.append(new_atom_ls)
    #             #apply new atom
    #             next_all_other_pats_ls = self.lang.evaluate_atom_ls_ls_on_dataset(reorg_atom_ls_ls, all_other_pats_ls)
    #             # next_program = program.copy() + [self.dqn.atom_to_vector(atom)]
    #             # next_program_str = program_str.copy() + [self.lang.atom_to_str(atom)]
    #             #check constraints
    #             # x_cons = self.check_x_constraint_with_atom_ls(X_pd, program_atom_ls, lang) #is e(r)?
    #             prog_cons = self.check_program_constraint(next_program) #is len(e) < 10
    #             db_cons = self.check_db_constrants_ls(next_all_other_pats_ls, y) #entropy
    #             #derive reward
    #             reward = db_cons# if x_cons else 0 # NOTE: these become part of reward
    #             done = atom["formula"] == "end" or not prog_cons# or not x_cons # NOTE: Remove reward check
    #             #record transition in buffer
    #             if done:
    #                 next_program = None
    #             transition = Transition(X, X_pd_ls,program, (atom, origin_atom), next_program, reward)
    #             self.dqn.observe_transition(transition)
    #             #update model
    #             loss = self.dqn.optimize_model_ls()
    #             # print(loss)
    #             sum_loss += loss
    #             #update next step
    #             if done: #stopping condition
    #                 # if reward > 0.5: success += 1
    #                 # else: failure += 1
    #                 success += np.sum(reward > 0.5)
    #                 break
    #             else:
    #                 program = next_program
    #                 program_str = next_program_str
    #                 all_other_pats_ls = next_all_other_pats_ls

    #         # Update the target net
    #         if episode_i % self.target_update == 0:
    #             self.dqn.update_target()
    #         # Print information
    #         total_count = ((episode_i + 1)*self.batch_size)
    #         success_rate = (success / ((episode_i + 1)*self.batch_size)) * 100.0
    #         avg_loss = sum_loss/(episode_i+1)
    #         desc = f"[Train Epoch {epoch}] Avg Loss: {avg_loss}, Success: {success}/{total_count} ({success_rate:.2f}%)"
    #         iterator.set_description(desc)
    #     if self.is_log:
    #         self.logger.log(level=logging.DEBUG, msg = desc)
    #     self.epsilon *= self.epsilon_falloff

    def process_curr_atoms(self, atom_ls, program, program_str, all_other_pats_ls, program_col_ls, X_pd_ls, outbound_mask_ls):
        # if not self.do_medical:    
        curr_atom_str_ls = self.lang.atom_to_str_ls_full(X_pd_ls, atom_ls, col_key, op_key, pred_v_key, self.train_dataset.feat_range_mappings, self.train_dataset.cat_id_unique_vals_mappings)
        # else:
        #     curr_atom_str_ls = self.lang.atom_to_str_ls_full_medical(atom_ls, col_key, range_key, self.train_dataset.feat_range_mappings)
        
        # outbound_mask_ls = atom_ls[outbound_key]
        
        next_program = program.copy()
        
        next_outbound_mask_ls=outbound_mask_ls.copy()
        
        next_program_str = program_str.copy()
        
        curr_vec_ls = self.dqn.atom_to_vector_ls0(atom_ls)

        if len(program) > 0:                        
            next_program, program_col_ls, next_program_str, next_outbound_mask_ls = self.integrate_curr_program_with_prev_programs(next_program, curr_vec_ls, atom_ls, program_col_ls, next_program_str, curr_atom_str_ls, next_outbound_mask_ls)
        else:
            next_program.append(curr_vec_ls)
            next_outbound_mask_ls.append(atom_ls[outbound_key])
            for vec_idx in range(len(curr_vec_ls)):
                # vec = curr_vec_ls[vec_idx]
                atom_str = curr_atom_str_ls[vec_idx]
                for k in range(len(atom_ls[col_key][vec_idx])):
                    program_col_ls[vec_idx][k].append(atom_ls[col_key][vec_idx][k])
                    next_program_str[vec_idx][k].append(atom_str[k])
        # if not self.do_medical:
        next_all_other_pats_ls,_ = self.lang.evaluate_atom_ls_ls_on_dataset_full_multi(atom_ls, all_other_pats_ls, col_key, op_key, pred_v_key)
        # else:
        #     next_all_other_pats_ls = self.lang.evaluate_atom_ls_ls_on_dataset_full_multi_medicine(atom_ls, all_other_pats_ls, col_key, range_key)
        return next_program, next_program_str, next_all_other_pats_ls, program_col_ls, next_outbound_mask_ls

    def compute_auc_acc(self, all_outcome_arr, all_pred_outcome_arr, all_treatment_arr, all_pred_treatment_arr):
        all_outcome_arr_np = torch.cat(all_outcome_arr).view(-1).numpy()
        all_pred_outcome_arr_full = torch.cat(all_pred_outcome_arr)           
        all_pred_outcome_arr_full_d = (all_pred_outcome_arr_full > 0.5).type(torch.long).view(-1).numpy()
        outcome_acc = np.mean(all_outcome_arr_np == all_pred_outcome_arr_full_d)
        if len(np.unique(all_outcome_arr_np)) <= 1:
            outcome_auc = 0
        else:
            outcome_auc = roc_auc_score(all_outcome_arr_np, all_pred_outcome_arr_full.numpy())
        
        all_treatment_arr_np = torch.cat(all_treatment_arr).view(-1).numpy()
        all_pred_treatment_arr_full = torch.cat(all_pred_treatment_arr)
        all_pred_treatment_arr_full_d = (all_pred_treatment_arr_full > 0.5).type(torch.long).view(-1).numpy()
        treatment_acc = np.mean(all_treatment_arr_np == all_pred_treatment_arr_full_d)
        if len(np.unique(all_treatment_arr_np)) <= 1:
            treatment_auc = 0
        else:
            treatment_auc = roc_auc_score(all_treatment_arr_np, all_pred_treatment_arr_full.numpy())
        
        return outcome_auc, outcome_acc, treatment_auc, treatment_acc

    def train_epoch(self, epoch, train_loader):
        success, failure, sum_loss = 0, 0, 0.
        
        iterator = tqdm(enumerate(train_loader), desc="Training Synthesizer", total=len(train_loader))
        
        sum_loss = 0

        all_outcome_arr = []
        all_treatment_arr = []
        all_obs_arr = []
        all_pred_outcome_arr = []
        all_pred_treatment_arr = []
        all_pred_obs_arr = []


        for episode_i, b in iterator:
        # for i, b in tqdm.tqdm(enumerate(iterator)):
            X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask = data_utils.post_process_batch(b["df"], b["pid"], b["batch_ids"], self.numer_feat_ls, self.cat_feat_ls, self.cat_feat_ls_onehot, self.feat_to_onehot_embedding, ["label"], ["concat_treatment_label_id"], return_cat_numeric_feat=True)
            
            X = X.to(self.device)
            M = M.to(self.device)
            outcome_arr = outcome_arr.to(self.device)
            treatment_arr = treatment_arr.to(self.device)
            
            
            obs_idx = b["batch_ids"]
            cov      = torch.zeros(len(pd.unique(b["df"]["PAT_ID"]))).unsqueeze(1).to(self.device)

            all_other_pats_ls = b["other_df"]
            # (all_other_pats_ls, X_pd_ls, X, X_sample_ids, (X_num, X_cat), _), y = val
            all_other_pats_ls, all_other_pats_ids_ls_ls = self.copy_data_in_database(all_other_pats_ls, id_attr="PAT_ID", time_attr="num_days", label_attr="concat_treatment_label")
            X_feat_embedding = None
            # if self.train_feat_embeddings is not None:
            #     X_feat_embedding = self.train_feat_embeddings[X_sample_ids]
            
            # (all_other_pats, X_pd, X), y = self.train_dataset[all_rand_ids[sample_idx].item()]
            
            
            # X_pd_full = self.train_dataset.all_r_data #b["df"]#pd.concat(X_pd_ls)
            X_pd_full = b["df"]
            
            X_pd_ls = b["df_ls"]
            

            X_ids = list(X_pd_full["PAT_ID"])
            
            pid_ls = b["pid"]
            
            # col_comp_ls = zip()
            # while True: # episode
            # for 
            # for col_id in col_ids:
            # random.shuffle(col_op_ls)
            # last_col , last_op  = col_op_ls[-1]

            if X_feat_embedding is None:
                loss, path_t, path_p, path_h, path_outcome, path_treatment, gt_path_outcome, gt_path_treatment = self.dqn.predict_atom_ls(data=(train_loader.dataset.all_r_data, pid_ls, X_pd_full, obs_idx, cov, X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask, all_other_pats_ls, all_other_pats_ids_ls_ls, self.numer_feat_ls, self.cat_feat_ls, None, None), X_pd_ls=X_pd_full, epsilon=self.epsilon, id_attr="PAT_ID", time_attr="num_days", trainer=self, train=True)
            else:
                loss, path_t, path_p, path_h, path_outcome, path_treatment, gt_path_outcome, gt_path_treatment = self.dqn.predict_atom_ls(data=(train_loader.dataset.all_r_data, pid_ls, X_pd_full, obs_idx, cov, X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask, all_other_pats_ls, all_other_pats_ids_ls_ls, self.numer_feat_ls, self.cat_feat_ls, None, None), X_pd_ls=X_pd_full, epsilon=self.epsilon, train=True)
            
            # path_t = np.around(path_t,str(self.dqn.params_dict["delta_t"])[::-1].find('.')).astype(np.float32)
            # p_val, outcome_pred_val, treatment_pred_val  = data_utils.extract_from_path(path_t,path_p, path_outcome,path_treatment,times,b["batch_ids"])
            sum_loss += loss
            # all_outcome_arr.append(outcome_arr.view(-1).detach().cpu())
            all_outcome_arr.append(gt_path_outcome.view(-1).detach().cpu())
            # all_treatment_arr.append(treatment_arr.view(-1).detach().cpu())
            all_treatment_arr.append(gt_path_treatment.view(-1).detach().cpu())
            # all_treatment_arr.append(torch.from_numpy(np.array(b["df"]["concat_treatment_label_id"])))
            all_obs_arr.append(X.cpu())
            
            all_pred_outcome_arr.append(path_outcome.view(-1).detach().cpu())
            all_pred_treatment_arr.append(path_treatment.view(-1).detach().cpu())
            all_pred_obs_arr.append(path_p[:,0:self.dqn.policy_net.all_input_feat_len].cpu())
            
            
            outcome_auc, outcome_acc, treatment_auc, treatment_acc = self.compute_auc_acc(all_outcome_arr, all_pred_outcome_arr, all_treatment_arr, all_pred_treatment_arr)
            
            
            obs_err = torch.mean((torch.cat(all_obs_arr) - torch.cat(all_pred_obs_arr))**2)
            
            avg_loss = sum_loss/(episode_i+1)
            desc = f"[Train epoch {epoch}] training loss:{avg_loss} outcome accuracy: {outcome_acc}, outcome auc score:{outcome_auc}, treatment accuracy:{treatment_acc}, treatment auc: {treatment_auc} observation error: {obs_err}"
            iterator.set_description(desc)
            torch.cuda.empty_cache()
            # if episode_i % self.target_update == 0:
                

        self.epsilon *= self.epsilon_falloff
            # for arr_idx in range(len(col_op_ls)):
            # for arr_idx in range(self.program_max_len):
            #     # (col, op) = col_op_ls[arr_idx]
            #     # col_name = col_list[col_id]
                
                
            #     # curr_atom_str_ls = self.lang.atom_to_str_ls_full(atom_ls, col_key, op_key, pred_v_key, self.train_dataset.feat_range_mappings)
                
            #     # next_program = program.copy()
                
            #     # next_program_str = program_str.copy()
                
            #     # curr_vec_ls = self.dqn.atom_to_vector_ls0(atom_ls)

            #     # if len(program) > 0:                        
            #     #     next_program, program_col_ls, next_program_str= self.integrate_curr_program_with_prev_programs(next_program, curr_vec_ls, atom_ls, program_col_ls, next_program_str, curr_atom_str_ls)
            #     # else:
            #     #     next_program.append(curr_vec_ls)
            #     #     for vec_idx in range(len(curr_vec_ls)):
            #     #         # vec = curr_vec_ls[vec_idx]
            #     #         atom_str = curr_atom_str_ls[vec_idx]
            #     #         for k in range(len(atom_ls[col_key][vec_idx])):
            #     #             program_col_ls[vec_idx][k].append(atom_ls[col_key][vec_idx][k])
            #     #             next_program_str[vec_idx][k].append(atom_str[k])
                
            #     # next_all_other_pats_ls = self.lang.evaluate_atom_ls_ls_on_dataset_full_multi(atom_ls, all_other_pats_ls, col_key, op_key, pred_v_key)
            #     next_program, next_program_str, next_all_other_pats_ls, program_col_ls, next_outbound_mask_ls = self.process_curr_atoms(atom_ls, program, program_str, all_other_pats_ls, program_col_ls, X_pd_ls, outbound_mask_ls)
            #     db_cons = self.check_db_constrants_ls(next_all_other_pats_ls, y) #entropy
            #     #derive reward
            #     if not self.multilabel:
            #         reward = db_cons# if x_cons else 0 # NOTE: these become part of reward
            #     else:
            #         reward = np.mean(db_cons,axis=-1)
            #     done = (arr_idx == self.program_max_len-1)
            #     #record transition in buffer
            #     if done:
            #         next_state = None
            #         next_program = None
            #     else:
            #         next_state = (next_program, next_outbound_mask_ls)
            #     if X_feat_embedding is None:
            #         transition = Transition((X, X_num, X_cat), X_pd_full,(program, outbound_mask_ls), atom_ls, next_state, reward - prev_reward)
            #     else:
            #         transition = Transition((X, X_feat_embedding), X_pd_full,(program, outbound_mask_ls), atom_ls, next_state, reward - prev_reward)
            #     self.dqn.observe_transition(transition)
            #     #update model
            #     loss = self.dqn.optimize_model_ls0()
            #     # print(loss)
            #     sum_loss += loss
            #     #update next step
            #     if done: #stopping condition
            #         # if reward > 0.5: success += 1
            #         # else: failure += 1
            #         if not self.multilabel:
            #             success += np.sum(np.max(reward, axis = -1) > 0.5)
            #         else:
            #             success += np.sum(db_cons > 0.5)
            #         break
            #     else:
            #         program = next_program
            #         program_str = next_program_str
            #         all_other_pats_ls = next_all_other_pats_ls
            #         prev_reward = reward
            #         outbound_mask_ls = next_outbound_mask_ls
            # # Update the target net
            # if episode_i % self.target_update == 0:
            #     self.dqn.update_target()
            # Print information
        #     total_count = ((episode_i + 1)*self.batch_size)
        #     success_rate = (success / ((episode_i + 1)*self.batch_size)) * 100.0
        #     avg_loss = sum_loss/(episode_i+1)
        #     desc = f"[Train Epoch {epoch}] Avg Loss: {avg_loss}, Success: {success}/{total_count} ({success_rate:.2f}%)"
        #     iterator.set_description(desc)
        # if self.is_log:
        #     self.logger.log(level=logging.DEBUG, msg = desc)
        

    
    def test_epoch(self, epoch):
        success, failure, sum_loss = 0, 0, 0.
        iterator = tqdm(enumerate(self.test_dataset), desc="Testing Synthesizer", total=len(self.test_dataset))
        y_true_ls=[]
        y_pred_ls=[]
        self.dqn.policy_net.eval()
        self.dqn.target_net.eval()
        with torch.no_grad():
            for episode_i, val in iterator:
                # if episode_i == 28:
                #     print()
                (all_other_pats, X_pd, X), y = val
                program = []
                program_str = []
                program_atom_ls = []
                while True: # episode
                    atom = self.dqn.predict_atom(features=X, X_pd=X_pd, program=program, epsilon=0)
                    atom_ls = self.identify_op(X_pd, atom)
                    next_program = program.copy()
                    next_program_str = program_str.copy()
                    for new_atom in atom_ls:
                        next_program = next_program + [self.dqn.atom_to_vector(new_atom)]
                        # atom["num_op"] = atom_op
                        
                        
                        next_program_str = next_program_str + [self.lang.atom_to_str(new_atom)]
                        
                        program_atom_ls.append(new_atom)
                    #apply new atom
                    next_all_other_pats = self.lang.evaluate_atom_ls_on_dataset(program_atom_ls, all_other_pats)
                    # next_program = program.copy() + [self.dqn.atom_to_vector(atom)]
                    # next_program_str = program_str.copy()+[self.lang.atom_to_str(atom)]
                    #check constraints
                    # x_cons = self.check_x_constraint_with_atom_ls(X_pd, program_atom_ls, lang) #is e(r)?
                    prog_cons = self.check_program_constraint(next_program) #is len(e) < 10
                    y_pred = self.get_test_decision_from_db(next_all_other_pats)# if x_cons else -1
                    db_cons = self.check_db_constrants(next_all_other_pats, y=y_pred)  # entropy
                    #derive reward
                    done = atom["formula"] == "end" or not prog_cons# or not x_cons # NOTE: Remove reward check
                    if done:
                        next_program = None
                    #update next step
                    if done: #stopping condition
                        if self.is_log:
                            msg = "Test Epoch {},  Label: {}, Prediction: {}, Match Score:{:7.4f}, Patient Info: {}, Explanation: {}".format(epoch, int(y[0]), y_pred, db_cons, str(X_pd.to_dict()),str(next_program_str))
                            self.logger.log(level=logging.DEBUG, msg=msg)
                        if y == y_pred: success += 1
                        else: failure += 1
                        y_true_ls.append(y.item())
                        y_pred_ls.append(y_pred)
                        break
                    else:
                        program = next_program
                        program_str = next_program_str
                        all_other_pats = next_all_other_pats

                y_true_array = np.array(y_true_ls, dtype=float)
                y_pred_array = np.array(y_pred_ls, dtype=float)
                y_pred_array[y_pred_array < 0] = 0.5
                if np.sum(y_pred_array == 1) <= 0 or np.sum(y_true_array == 1) <= 0:
                #     recall = 0
                #     f1 = 0
                    auc_score= 0
                else:
                    auc_score = roc_auc_score(y_true_array, y_pred_array)

                # if episode_i == self.batch_size:
                #     print(y_true_array.reshape(-1))
                #     print(y_pred_array.reshape(-1))

                # Print information
                success_rate = (success / (episode_i + 1)) * 100.00
                avg_loss = sum_loss/(episode_i+1)
                desc = f"[Test Epoch {epoch}] Avg Loss: {avg_loss}, Success: {success}/{episode_i + 1} ({success_rate:.2f}%), auc score: {auc_score}"
                iterator.set_description(desc)
        if self.is_log:
            self.logger.log(level=logging.DEBUG, msg = desc)
            
        self.dqn.policy_net.train()
        self.dqn.target_net.train()
        return y_pred_array
    
    def integrate_curr_program_with_prev_programs(self, next_program, curr_vec_ls, atom_ls, program_col_ls, next_program_str, curr_atom_str_ls, next_outbound_mask_ls):
        prev_prog_ids = atom_ls[prev_prog_key].cpu()
        curr_col_ids = atom_ls[col_key]
        outbound_mask = atom_ls[outbound_key]
        program = []
        outbound_mask_ls = []
        sample_ids = torch.arange(len(next_program[0]))
        # program length
        for pid in range(len(next_program)):
            program.append(torch.stack([next_program[pid][sample_ids, prev_prog_ids[:,k]] for k in range(prev_prog_ids.shape[-1])],dim=1))
            outbound_mask_ls.append(torch.stack([next_outbound_mask_ls[pid][sample_ids, prev_prog_ids[:,k]] for k in range(prev_prog_ids.shape[-1])], dim=-1))
        program.append(curr_vec_ls)
        outbound_mask_ls.append(outbound_mask)
        new_program_col_ls = []
        new_program_str = []
        for idx in range(len(program_col_ls)):
            curr_sample_new_program_col_ls = []
            curr_sample_new_program_str = []
            for k in range(self.topk_act):
                curr_new_program_col_ls = []
                curr_new_program_str = []
                # for pid in range(len(program_col_ls[idx])):
                
                #     curr_new_program_col_ls.append(program_col_ls[idx][prev_prog_ids[idx,k].item()][pid])
                #     # [k].append()
                #     curr_new_program_str.append(next_program_str[idx][prev_prog_ids[idx,k].item()][pid])
                curr_new_program_col_ls.extend(program_col_ls[idx][prev_prog_ids[idx,k].item()])
                curr_new_program_str.extend(next_program_str[idx][prev_prog_ids[idx,k].item()])
                
                
                curr_new_program_col_ls.append(curr_col_ids[idx][k])
                curr_new_program_str.append(curr_atom_str_ls[idx][k])
                curr_sample_new_program_col_ls.append(curr_new_program_col_ls)
                curr_sample_new_program_str.append(curr_new_program_str)
            new_program_col_ls.append(curr_sample_new_program_col_ls)
            new_program_str.append(curr_sample_new_program_str)
        return program, new_program_col_ls, new_program_str, outbound_mask_ls

    def copy_data_in_database(self, all_other_pats_ls, id_attr, time_attr, label_attr):
        all_other_pats_full_ls_ls = []
        all_other_pats_ids_ls_ls = []
        for idx in range(len(all_other_pats_ls)):
            curr_other_pats_full_ls = []
            curr_other_pats_ids_ls = []
            for k in range(self.topk_act):
                pat_temporal_join_info = pd.merge(all_other_pats_ls[idx], all_other_pats_ls[idx], on=[id_attr], suffixes=("", "_before"))
                
                pat_temporal_join_info = pat_temporal_join_info.loc[pat_temporal_join_info[time_attr] >= pat_temporal_join_info[time_attr+"_before"]]
                
                pat_temporal_join_info.drop_duplicates(inplace=True)

                curr_other_pats_full_ls.append(pat_temporal_join_info)

                curr_other_pats_ids_ls.append(pat_temporal_join_info[[id_attr, time_attr, label_attr]].drop_duplicates())
            
            all_other_pats_full_ls_ls.append(curr_other_pats_full_ls)

            all_other_pats_ids_ls_ls.append(curr_other_pats_ids_ls)
            
        return all_other_pats_full_ls_ls, all_other_pats_ids_ls_ls
    
    def concatenate_program_across_samples(self, generated_program_ls, generated_program_str_ls, program_label_ls):
        full_program_ls = []
        full_program_str_ls = []
        full_label_ls = []
        # for k in range(len(generated_program_ls[0])):
        #     curr_full_program_ls = []
        #     curr_full_program_str_ls = []
        #     curr_full_label_ls = []
        #     for idx in range(len(generated_program_ls)):
        #         curr_full_program_ls.append(generated_program_ls[idx][k].view(-1,generated_program_ls[idx][k].shape[-1]))
        #         curr_full_label_ls.append(program_label_ls[idx][:,k].unsqueeze(1).repeat(1, generated_program_ls[idx][k].shape[1]).view(-1, 1))
        #         curr_generated_program_str_ls = []
        #         for i in range(len(generated_program_str_ls[idx])):
        #             sub_curr_generated_program_str_ls = []
        #             for j in range(len(generated_program_str_ls[idx][0])):
        #                 sub_curr_generated_program_str_ls.append(generated_program_str_ls[idx][i][j][k])
                    
        #             curr_generated_program_str_ls.append(sub_curr_generated_program_str_ls)
                    
        #         curr_full_program_str_ls.extend(curr_generated_program_str_ls)
            
        #     full_program_str_ls.extend(curr_full_program_str_ls)
        #     full_program_ls.append(torch.cat(curr_full_program_ls))
        #     full_label_ls.append(torch.cat(curr_full_label_ls))
        
        for idx in range(len(generated_program_ls)):
            full_program_ls.append(torch.stack(generated_program_ls[idx]))
            full_label_ls.append(torch.cat(program_label_ls[idx]))
        for p_str_ls in generated_program_str_ls:
            full_program_str_ls.extend(p_str_ls)
        
        
        
        return torch.cat(full_program_ls), full_program_str_ls, torch.cat(full_label_ls)
    
    def decode_program_to_str(self, single_program):
        program_str = self.dqn.vector_ls_to_str_ls0(single_program)
        return program_str

    def redundancy_metrics(self, existing_data, target_data):
        if len(existing_data) == len(target_data):
            return True
        # existing_accuracy = np.mean(existing_data["label"])
        # target_accuracy = np.mean(target_data["label"])
        # if np.abs(len(existing_data) - len(target_data)) <= (len(target_data)*0.02):
        #     return True
        return False

    def concat_all_elements(self, reduced_program_ls, reduced_program_str_ls, labels):
        flatten_reduced_program_ls = []
        flatten_reduced_program_str_ls = []
        flatten_labels = []
        for i in range(len(reduced_program_ls)):
            for j in range(len(reduced_program_ls[i])):
                for k in range(len(reduced_program_ls[i][j])):
                    flatten_reduced_program_ls.append(reduced_program_ls[i][j][k])
                    flatten_reduced_program_str_ls.append(reduced_program_str_ls[i][j][k])
                    flatten_labels.append(labels[i])
                    
        return flatten_reduced_program_ls, flatten_reduced_program_str_ls, flatten_labels
                

    def remove_redundant_predicates(self, all_other_pats_ls, all_transformed_expr_ls, next_all_other_pats_ls, next_program, next_program_str):
        transposed_expr_ls = []
        transposed_next_program = []
        for j in range(len(all_transformed_expr_ls[0])):
            curr_transposed_expr_ls = []
            curr_program_ls = []
            for k in range(len(all_transformed_expr_ls[0][0])):
                sub_curr_transposed_expr_ls = []
                sub_curr_program_ls = []
                for i in range(len(all_transformed_expr_ls)):
                    
                    sub_curr_transposed_expr_ls.append(all_transformed_expr_ls[i][j][k])
                    sub_curr_program_ls.append(next_program[i][j][k])
                curr_transposed_expr_ls.append(sub_curr_transposed_expr_ls)
                curr_program_ls.append(sub_curr_program_ls)
            
            transposed_expr_ls.append(curr_transposed_expr_ls)
            transposed_next_program.append(curr_program_ls)


        all_other_pats_ls, all_other_pats_ids_ls_ls = self.copy_data_in_database(all_other_pats_ls, id_attr="PAT_ID", time_attr="num_days", label_attr="concat_treatment_label")

        reduced_program_ls = []
        reduced_program_str_ls = []

        for i in range(len(transposed_expr_ls)):
            curr_reduced_program_ls = []
            curr_reduced_program_str_ls = []
            for j in range(len(transposed_expr_ls[i])):
                redundant_clause_id_ls = []
                sub_curr_reduced_program_ls = []
                sub_curr_reduced_program_str_ls = []

                for k in range(len(transposed_expr_ls[i][j])):
                    temp_expr_ls = transposed_expr_ls[i][j].copy()
                    del temp_expr_ls[k]
                    existing_data = all_other_pats_ls[i][j].copy()
                    for expr_c in temp_expr_ls:
                        curr_op = expr_c[1]
                        curr_const = expr_c[2]
                        expr = curr_op(existing_data[expr_c[0]], curr_const)
                        existing_data = self.lang.evaluate_expression_on_data(existing_data, expr)
                    if self.redundancy_metrics(existing_data, next_all_other_pats_ls[i][j]):
                        redundant_clause_id_ls.append(k)
                    else:
                        sub_curr_reduced_program_ls.append(transposed_next_program[i][j][k])
                        sub_curr_reduced_program_str_ls.append(next_program_str[i][j][k])
                curr_reduced_program_ls.append(sub_curr_reduced_program_ls)
                curr_reduced_program_str_ls.append(sub_curr_reduced_program_str_ls)
            reduced_program_ls.append(curr_reduced_program_ls)
            reduced_program_str_ls.append(curr_reduced_program_str_ls)
                
        return reduced_program_ls, reduced_program_str_ls

    def cluster_programs(self, full_program_ls, full_program_str_ls, full_label_ls):
        # full_label_ls_tensor = torch.cat(full_label_ls)
        # full_program_ls_tensor = torch.cat(full_program_ls)
        
        full_label_ls_tensor = full_label_ls
        full_program_ls_tensor = full_program_ls

        unique_labels = full_label_ls_tensor.unique().tolist()

        for label in unique_labels:

            print("print info for label ", str(label))

            curr_full_program_ls_tensor = full_program_ls_tensor[full_label_ls_tensor.view(-1) == label][0:-1]
            curr_idx_ls = torch.nonzero(full_label_ls_tensor.view(-1) == label).view(-1).tolist()
            cluster_assignment_ids, cluster_centroids = KMeans(curr_full_program_ls_tensor, K=5)
            approx_cluster_centroids, min_program_ids = get_closet_samples_per_clusters(cluster_centroids, curr_full_program_ls_tensor)
            for idx in range(len(min_program_ids.tolist())):
                selected_program_str = full_program_str_ls[curr_idx_ls[min_program_ids[idx]]]
                print("cluster idx %d:%s"%(idx, selected_program_str))
                print("cluster count for cluster idx %d:%d"%(idx, torch.sum(cluster_assignment_ids==idx).item()))

            program_str_ls = []
            for idx in range(len(cluster_centroids)):
                if len(torch.nonzero(cluster_centroids[idx])) <= 0:
                    continue

                program_str = self.decode_program_to_str(cluster_centroids[idx])
                print("cluster idx %d:%s"%(idx, program_str))
            # program_str_ls.append(program_str) 
        # return program_str_ls
        print()
        
    def test_epoch_ls(self, test_loader, epoch, exp_y_pred_arr = None, feat_embedding = None):
        pd.options.mode.chained_assignment = None

        success, failure, sum_loss = 0, 0, 0.

        iterator = tqdm(enumerate(test_loader), desc="Training Synthesizer", total=len(test_loader))
        # iterator = tqdm(enumerate(self.test_dataset), desc="Testing Synthesizer", total=len(self.test_dataset))
        y_true_ls=[]
        y_pred_ls=[]
        y_pred_prob_ls=[]
        # if self.rl_algorithm == "dqn":
        self.dqn.policy_net.eval()
        self.dqn.target_net.eval()
        # else:
        #     self.dqn.actor.eval()
        #     self.dqn.critic.eval()
            
        generated_program_ls = []
        generated_program_str_ls = []
        program_label_ls = []
        
        correct_outcome_pred = 0
        total_outcome_pred = 0
        correct_treatment_pred = 0 
        total_treatment_pred= 0 
        
        all_outcome_arr = []
        all_treatment_arr = []
        all_obs_arr = []
        all_pred_outcome_arr = []
        all_pred_treatment_arr = []
        all_pred_obs_arr = []
        
        with torch.no_grad():
            # col_list = list(self.train_dataset.data.columns)
        
            # op_ls = list([operator.__le__, operator.__ge__])
            
            # col_op_ls = []
            
            # last_col = None

            # last_op = None
            
            # for col in col_list:
            #     if col == "PAT_ID" or col == "label":
            #         continue
            #     last_col = col
            #     for op in op_ls:
            #         col_op_ls.append((col, op))
            #         last_op = op
            for episode_i, b_val in iterator:
                if len(b_val["df_val"]) <= 0:
                    continue
                X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask = data_utils.post_process_batch(b_val["df"], b_val["pid"], b_val["batch_ids"], self.numer_feat_ls, self.cat_feat_ls, self.cat_feat_ls_onehot, self.feat_to_onehot_embedding, ["label"], ["concat_treatment_label_id"], return_cat_numeric_feat=True)
            
                X = X.to(self.device)
                M = M.to(self.device)
                outcome_arr = outcome_arr.to(self.device)
                treatment_arr = treatment_arr.to(self.device)
                # if "Z1166319" in b_val["pid"]:
                #     print()
                
                X_val, M_val, outcome_arr_val, gt_treatment_arr_val, unique_times_val, times_val, treatment_arr_val, time_ptr_val = data_utils.post_process_batch_val(b_val["df_val"], b_val["pid"], b_val["batch_ids_val"], self.numer_feat_ls, self.cat_feat_ls, self.cat_feat_ls_onehot, self.feat_to_onehot_embedding, ["label"], ["concat_treatment_label_id"])

                X_val = X_val.to(self.device)
                M_val = M_val.to(self.device)

                outcome_arr_val = outcome_arr_val.to(self.device)
                gt_treatment_arr_val = gt_treatment_arr_val.to(self.device)

                obs_idx = b_val["batch_ids"]
                cov      = torch.zeros(len(pd.unique(b_val["df"]["PAT_ID"]))).unsqueeze(1).to(self.device)

                all_other_pats_ls = b_val["other_df"]
                # (all_other_pats_ls, X_pd_ls, X, X_sample_ids, (X_num, X_cat), _), y = val
                all_other_pats_ls, all_other_pats_ids_ls_ls = self.copy_data_in_database(all_other_pats_ls, id_attr="PAT_ID", time_attr="num_days", label_attr="concat_treatment_label")
                X_feat_embedding = None
                
                # X_pd_full = test_loader.dataset.all_r_data #b["df"]#pd.concat(X_pd_ls)

                X_pd_full = b_val["df"]
                
                X_pd_ls = b_val["df_ls"]
                
                X_ids = list(X_pd_full["PAT_ID"])
                
                pid_ls = b_val["pid"]

                if X_feat_embedding is None:
                    loss, path_t, path_p, path_h, path_outcome, path_treatment = self.dqn.predict_atom_ls(data=(test_loader.dataset.other_set, pid_ls, X_pd_full, obs_idx, cov, X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask, all_other_pats_ls, all_other_pats_ids_ls_ls, self.numer_feat_ls, self.cat_feat_ls, unique_times_val, treatment_arr_val), X_pd_ls=X_pd_full, epsilon=0, id_attr="PAT_ID", time_attr="num_days", trainer=self, train=False, time_ptr_val=time_ptr_val, obs_idx_val=b_val["batch_ids_val"].copy(), outcome_arr_val=outcome_arr_val.clone(), X_pd_val=b_val["df_val"].copy(), all_times_val = times_val.copy())
                else:
                    loss, path_t, path_p, path_h, path_outcome, path_treatment = self.dqn.predict_atom_ls(data=(test_loader.dataset.other_set, pid_ls, X_pd_full, obs_idx, cov, X, M, outcome_arr, treatment_arr, times, time_ptr, X_num, X_num_mask, X_cat, X_cat_mask, all_other_pats_ls, all_other_pats_ids_ls_ls, self.numer_feat_ls, self.cat_feat_ls, unique_times_val, treatment_arr_val), X_pd_ls=X_pd_full, epsilon=0, train=False, time_ptr_val=time_ptr_val, obs_idx_val=b_val["batch_ids_val"].copy(), outcome_arr_val=outcome_arr_val.clone(), X_pd_val=b_val["df_val"].copy(), all_times_val = times_val.copy())
                
                # path_t = np.around(path_t,str(self.dqn.params_dict["delta_t"])[::-1].find('.')).astype(np.float32)
                # p_val, outcome_pred_val, treatment_pred_val  = data_utils.extract_from_path(path_t,path_p, path_outcome,path_treatment,times,b["batch_ids"])
                sum_loss += loss

                path_t = np.around(path_t,str(self.dqn.params_dict["delta_t"])[::-1].find('.')).astype(np.float32) #Round floating points error in the time vector.

                p_val, outcome_pred_val, treatment_pred_val  = data_utils.extract_from_path(path_t,path_p, path_outcome,path_treatment,times_val,b_val["batch_ids_val"])
                m, v      = torch.chunk(p_val,2,dim=1)       
                last_loss = (data_utils.log_lik_gaussian(X_val,m,v)*M_val).sum()
                mse_loss  = (torch.pow(X_val - m, 2) * M_val).mean()
                curr_outcome_loss = torch.nn.BCEWithLogitsLoss()(outcome_pred_val.view(-1), outcome_arr_val.view(-1).type(torch.float))
                correct_outcome_pred += torch.sum((outcome_pred_val > 0.5).type(torch.long).view(-1) == outcome_arr_val.type(torch.long).view(-1)).item()
                total_outcome_pred += len(outcome_pred_val.view(-1))
                outcome_acc = correct_outcome_pred*1.0/total_outcome_pred
                avg_loss = sum_loss/(episode_i+1)
                # curr_treatment_loss = torch.nn.BCEWithLogitsLoss()(treatment_pred_val.view(-1), gt_treatment_arr_val.view(-1).type(torch.float))
                curr_treatment_loss = torch.nn.CrossEntropyLoss()(treatment_pred_val, gt_treatment_arr_val.view(-1).type(torch.float))
                correct_treatment_pred += torch.sum((treatment_pred_val > 0.5).type(torch.long).view(-1) == gt_treatment_arr_val.type(torch.long).view(-1)).item()
                total_treatment_pred += treatment_pred_val.shape[0] #len(treatment_pred_val.view(-1))
                treatment_acc = correct_treatment_pred*1.0/total_treatment_pred



                all_outcome_arr.append(outcome_arr_val.view(-1).detach().cpu())
                all_treatment_arr.append(gt_treatment_arr_val.view(-1).detach().cpu())
               
                all_pred_outcome_arr.append(outcome_pred_val.view(-1).detach().cpu())
                all_pred_treatment_arr.append(treatment_pred_val.view(-1).detach().cpu())
                
                outcome_auc, outcome_acc, treatment_auc, treatment_acc = self.compute_auc_acc(all_outcome_arr, all_pred_outcome_arr, all_treatment_arr, all_pred_treatment_arr)
                print(outcome_auc, outcome_acc, treatment_auc, treatment_acc)
                desc = f"[Test epoch {epoch}] test loss:{avg_loss} outcome accuracy: {outcome_acc}, outcome auc: {outcome_auc}, treatment accuracy:{treatment_acc}, treatment auc:{treatment_auc}, observation error: {mse_loss}"
                iterator.set_description(desc)


                # if self.is_log:
                #     id_attr="PAT_ID"
                #     time_attr="num_days"
                #     i_obs_val = b_val["batch_ids_val"]
                #     for r_idx in range(len(i_obs_val)):
                            
                #         # col_ls = list(set(program_col_ls[pat_idx]))
                #         # for program_idx in range(len(curr_pat_program_cols_ls)):
                            
                #         for k in range(self.topk_act):
                #             col_ls = program_col_ls[tid-1][i_obs_val[r_idx]][k]
                #             # col_ls = curr_pat_program_cols_ls[program_idx][k]
                #             col_ls.append("PAT_ID")
                #             col_ls = list(set(col_ls))
                #             # (x_pd_full[time_attr] <= obs_time) & (x_pd_full[time_attr] >= time_lb[idx][k].item())
                #             x_pat_sub = X_pd_ls.loc[(X_pd_ls[id_attr] == pid_ls[i_obs_val[r_idx]]) & (X_pd_ls[time_attr] == times_val[r_idx] - 0.1)][col_ls]
                #             x_pat_sub.reset_index(inplace=True)
                            
                #             for col in col_ls:
                #                 if not col == "PAT_ID":
                #                     if not col in self.cat_feat_ls:
                #                         x_pat_sub[col] = x_pat_sub[col]*(self.feat_range_mappings[col][1] - self.feat_range_mappings[col][0]) + self.feat_range_mappings[col][0]
                #                     else:
                #                         x_pat_sub[col] = self.test_dataset.cat_id_unique_vals_mappings[col][x_pat_sub[col].values[0]]#x_pat_sub[col]*(self.test_dataset.feat_range_mappings[col][1] - self.test_dataset.feat_range_mappings[col][0]) + self.test_dataset.feat_range_mappings[col][0]

                #             curr_sim_records = res_all_other_pat_ls[tid-1][i_obs_val[r_idx]][k][["PAT_ID", time_attr]]

                #             pat_count = len(curr_sim_records.apply(lambda row: str(row["PAT_ID"]) + ":" + str(row[time_attr]), axis=1).unique())#len(res_all_other_pat_ls[r_idx][k])

                #             x_pat_sub.to_csv(os.path.join(self.work_dir, "patient_" + str(pid_ls[i_obs_val[r_idx]]) + "_time_" + str(times_val[r_idx] - 0.1) + ".csv"))
                            
                #             msg = "Label: {}, Prediction: {:7.4f}, Matched Patient Count: {},  Patient Info: {}, Explanation of number {}: {}".format(int(outcome_arr_val.view(-1)[r_idx].item()), outcome_pred_val.view(-1)[r_idx].item(), pat_count, str(x_pat_sub.to_dict()), int(k), str(program_str[tid-1][i_obs_val[r_idx]][k]))
                #             self.logger.log(level=logging.DEBUG, msg=msg)
                # all_outcome_arr.append(outcome_arr.view(-1).detach().cpu())
                # all_treatment_arr.append(treatment_arr.view(-1).detach().cpu())
                # all_obs_arr.append(X.cpu())
                
                # all_pred_outcome_arr.append(path_outcome.view(-1).detach().cpu())
                # all_pred_treatment_arr.append(path_treatment.view(-1).detach().cpu())
                # all_pred_obs_arr.append(path_p[:,0:self.dqn.policy_net.all_input_feat_len].cpu())
                
                # outcome_acc = torch.mean((torch.cat(all_outcome_arr) == torch.cat(all_pred_outcome_arr)).type(torch.float))
                # treatment_acc = torch.mean((torch.cat(all_treatment_arr) == torch.cat(all_pred_treatment_arr)).type(torch.float))
                # obs_err = torch.mean((torch.cat(all_obs_arr) - torch.cat(all_pred_obs_arr))**2)
                
                # avg_loss = sum_loss/(episode_i+1)
                # desc = f"[Train epoch {epoch}] training loss:{avg_loss} outcome accuracy: {outcome_acc}, treatment accuracy:{treatment_acc}, observation error: {obs_err}"
                # iterator.set_description(desc)



        #     for episode_i, val in iterator:
        #         # if episode_i == 13:
        #         #     print()
        #         (origin_all_other_pats_ls, X_pd_ls, X, X_sample_ids, (X_num, X_cat), _), y = val
        #         all_other_pats_ls = self.copy_data_in_database(origin_all_other_pats_ls)
                
        #         # for x_pd_idx in range(len(X_pd_ls)):
        #         #     if np.sum(X_pd_ls[x_pd_idx]["PAT_ID"] == 277) >= 1:
        #         #         print(x_pd_idx)
        #         #         break                
        #         X_feat_embeddings = None
        #         if feat_embedding is not None:
        #             X_feat_embeddings = feat_embedding[X_sample_ids]
                
        #         # (all_other_pats, X_pd, X), y = self.train_dataset[all_rand_ids[sample_idx].item()]
        #         program = []
        #         outbound_mask_ls = []
        #         program_str = [[[] for _ in range(self.topk_act)] for _ in range(len(X_pd_ls))]
        #         program_col_ls = [[[] for _ in range(self.topk_act)] for _ in range(len(X_pd_ls))]
        #         # for p_k in range(len(program_str)):
        #         #     program_str[p_k].append([[] for _ in range(self.topk_act)])
        #         #     program_col_ls[p_k].append([[] for _ in range(self.topk_act)])
                
                
        #         X_pd_full = pd.concat(X_pd_ls)
        #         all_transformed_expr_ls = []
        #         # for arr_idx in range(len(col_op_ls)):
        #         for arr_idx in range(self.program_max_len):
        #             # (col, op) = col_op_ls[arr_idx]
        #             # col_name = col_list[col_id]
        #             if X_feat_embeddings is None:
        #                 if self.rl_algorithm == "dqn":
        #                     atom_ls = self.dqn.predict_atom_ls(features=(X, X_num, X_cat), X_pd_ls=X_pd_full, program=program, outbound_mask_ls=outbound_mask_ls, epsilon=0)
        #                 else:
        #                     atom_ls = self.dqn.predict_atom_ls(features=(X, X_num, X_cat), X_pd_ls=X_pd_full, program=program, outbound_mask_ls=outbound_mask_ls, train=False)
        #             else:
        #                 if self.rl_algorithm == "dqn":
        #                     atom_ls = self.dqn.predict_atom_ls(features=(X,X_feat_embeddings), X_pd_ls=X_pd_full, program=program, outbound_mask_ls=outbound_mask_ls, epsilon=0)
        #                 else:
        #                     atom_ls = self.dqn.predict_atom_ls(features=(X,X_feat_embeddings), X_pd_ls=X_pd_full, program=program, outbound_mask_ls=outbound_mask_ls, train=False)
                    
        #             # if not self.do_medical:
        #             curr_atom_str_ls = self.lang.atom_to_str_ls_full(X_pd_ls, atom_ls, col_key, op_key, pred_v_key, self.test_dataset.feat_range_mappings, self.test_dataset.cat_id_unique_vals_mappings)
        #             # else:
        #             #     curr_atom_str_ls = self.lang.atom_to_str_ls_full_medical(atom_ls, col_key, range_key, self.test_dataset.feat_range_mappings)
        #                 # curr_atom_str_ls = self.lang.atom_to_str_ls_full(atom_ls, col_key, op_key, pred_v_key, self.test_dataset.feat_range_mappings)

        #             next_program = program.copy()
        #             next_outbound_mask_ls = outbound_mask_ls.copy()
        #             next_program_str = program_str.copy()
        #             curr_vec_ls = self.dqn.atom_to_vector_ls0(atom_ls)
                    
        #             if len(program) > 0:                        
                        

        #                 next_program, program_col_ls, next_program_str, next_outbound_mask_ls = self.integrate_curr_program_with_prev_programs(next_program, curr_vec_ls, atom_ls, program_col_ls, next_program_str, curr_atom_str_ls, next_outbound_mask_ls)



        #             else:

        #                 next_program.append(curr_vec_ls)
        #                 next_outbound_mask_ls.append(atom_ls[outbound_key])

        #                 for vec_idx in range(len(curr_vec_ls)):
        #                     # vec = curr_vec_ls[vec_idx]
        #                     atom_str = curr_atom_str_ls[vec_idx]
        #                     for k in range(len(atom_ls[col_key][vec_idx])):
        #                         program_col_ls[vec_idx][k].append(atom_ls[col_key][vec_idx][k])
        #                         next_program_str[vec_idx][k].append(atom_str[k])
        #                     # next_program_str[vec_idx].append(atom_str)

                    
        #             # atom_ls_ls = self.identify_op_ls(X.shape[0], atom)
        #             # reorg_atom_ls_ls= [[] for _ in range(len(X_pd_ls))]

                    
                    
        #             # for new_atom_ls in atom_ls_ls:

        #             #     curr_vec_ls = self.dqn.atom_to_vector_ls0(new_atom_ls)

        #             #     next_program.append(torch.stack(curr_vec_ls))

        #             #     curr_atom_str_ls = self.lang.atom_to_str_ls(new_atom_ls)

                    
        #         # while True: # episode
        #         #     atom,_ = self.dqn.predict_atom_ls(features=X, X_pd_ls=X_pd_ls, program=program, epsilon=0)
        #         #     atom_ls_ls = self.identify_op_ls(X.shape[0], atom)
        #         #     reorg_atom_ls_ls= [[] for _ in range(len(X_pd_ls))]

        #         #     next_program = program.copy()
        #         #     next_program_str = program_str.copy()
        #         #     for new_atom_ls in atom_ls_ls:

        #         #         curr_vec_ls = self.dqn.atom_to_vector_ls(new_atom_ls)

        #         #         next_program.append(torch.stack(curr_vec_ls))

        #         #         curr_atom_str_ls = self.lang.atom_to_str_ls(new_atom_ls)

        #         #         for vec_idx in range(len(curr_vec_ls)):
        #         #             vec = curr_vec_ls[vec_idx]
        #         #             atom_str = curr_atom_str_ls[vec_idx]
                            
        #         #             next_program_str[vec_idx].append(atom_str)
        #         #             program_atom_ls[vec_idx].append(new_atom_ls[vec_idx])
        #         #             reorg_atom_ls_ls[vec_idx].append(new_atom_ls[vec_idx])
        #                 # atom["num_op"] = atom_op
                        
                        
        #                 # next_program_str = next_program_str + []
                        
        #                 # program_atom_ls.append(new_atom_ls)
        #             #apply new atom
        #             # next_all_other_pats_ls = self.lang.evaluate_atom_ls_ls_on_dataset_full(atom_ls, all_other_pats_ls, col_key, op_key, pred_v_key)
        #             # if not self.do_medical:
        #             next_all_other_pats_ls, transformed_expr_ls = self.lang.evaluate_atom_ls_ls_on_dataset_full_multi(atom_ls, all_other_pats_ls, col_key, op_key, pred_v_key)
        #             # else:
        #             #     next_all_other_pats_ls =  self.lang.evaluate_atom_ls_ls_on_dataset_full_multi_medicine(atom_ls, all_other_pats_ls, col_key, range_key)
        #             # next_program = program.copy() + [self.dqn.atom_to_vector(atom)]
        #             # next_program_str = program_str.copy() + [self.lang.atom_to_str(atom)]
        #             #check constraints
        #             # x_cons = self.check_x_constraint_with_atom_ls(X_pd, program_atom_ls, lang) #is e(r)?
        #             # prog_cons = self.check_program_constraint(next_program) #is len(e) < 10
        #             # db_cons = self.check_db_constrants_ls(next_all_other_pats_ls, y) #entropy
        #             # y_pred = self.get_test_decision_from_db(next_all_other_pats_ls) if x_cons else -1
        #             y_pred, y_pred_prob = self.get_test_decision_from_db_ls_multi(next_all_other_pats_ls)
        #             # final_y_pred,_ = stats.mode(np.array(y_pred), axis = -1)
        #             # final_y_pred_prob = np.mean(np.array(y_pred_prob), axis = -1)
                    
        #             # done = atom["formula"] == "end" or not prog_cons# or not x_cons # NOTE: Remove reward check
        #             # done = (col == last_col) and (op == last_op)
        #             done = (arr_idx == self.program_max_len - 1)

        #             all_transformed_expr_ls.append(transformed_expr_ls)
        #             # if done:
        #             #     next_program = None
        #             #update next step
        #             if done: #stopping condition
                        
                        
                        
        #                 if self.is_log:
        #                     reduced_program_ls, reduced_program_str_ls = self.remove_redundant_predicates(origin_all_other_pats_ls, all_transformed_expr_ls, next_all_other_pats_ls, next_program, next_program_str)
        #                     flatten_reduced_program_ls, flatten_reduced_program_str_ls, flatten_label_ls = self.concat_all_elements(reduced_program_ls, reduced_program_str_ls, y)
                            
        #                     generated_program_ls.append(flatten_reduced_program_ls)
        #                     generated_program_str_ls.append(flatten_reduced_program_str_ls)
        #                     program_label_ls.append(flatten_label_ls)
        #                     save_data_path = os.path.join(self.work_dir, "save_data_dir/")
        #                     os.makedirs(save_data_path, exist_ok=True)


        #                     for pat_idx in range(len(y_pred)):
        #                         curr_pat_program_cols_ls = program_col_ls[pat_idx]
        #                         # col_ls = list(set(program_col_ls[pat_idx]))
        #                         for program_idx in range(len(curr_pat_program_cols_ls)):
        #                             col_ls = curr_pat_program_cols_ls[program_idx]
        #                             col_ls.append("PAT_ID")
        #                             col_ls = list(set(col_ls))
        #                             x_pat_sub = X_pd_ls[pat_idx][col_ls]
        #                             x_pat_sub.reset_index(inplace=True)
                                    
        #                             for col in col_ls:
        #                                 if not col == "PAT_ID":
        #                                     if not col in self.test_dataset.cat_cols:
        #                                         x_pat_sub[col] = x_pat_sub[col]*(self.test_dataset.feat_range_mappings[col][1] - self.test_dataset.feat_range_mappings[col][0]) + self.test_dataset.feat_range_mappings[col][0]
        #                                     else:
        #                                         x_pat_sub[col] = self.test_dataset.cat_id_unique_vals_mappings[col][x_pat_sub[col].values[0]]#x_pat_sub[col]*(self.test_dataset.feat_range_mappings[col][1] - self.test_dataset.feat_range_mappings[col][0]) + self.test_dataset.feat_range_mappings[col][0]

        #                             pat_count = len(next_all_other_pats_ls[pat_idx][program_idx])

        #                             x_pat_sub.to_csv(os.path.join(save_data_path, "patient_" + str(list(X_pd_ls[pat_idx]["PAT_ID"])[0]) + ".csv"))
                                    
        #                             msg = "Test Epoch {},  Label: {}, Prediction: {}, Match Score:{:7.4f}, Matched Patient Count: {},  Patient Info: {}, Explanation of number {}: {}".format(epoch, int(y[pat_idx]), y_pred[pat_idx], y_pred_prob[pat_idx], pat_count, str(x_pat_sub.to_dict()), int(program_idx), str(reduced_program_str_ls[pat_idx][program_idx]))
        #                             self.logger.log(level=logging.DEBUG, msg=msg)
        #                 # if y == y_pred: success += 1
        #                 # else: failure += 1
        #                 if not self.multilabel:
        #                     success += np.sum(y.view(-1).numpy() == np.array(y_pred).reshape(-1))
        #                     failure += np.sum(y.view(-1).numpy() != np.array(y_pred).reshape(-1))
        #                     y_true_ls.extend(y.view(-1).tolist())
        #                     y_pred_ls.extend(y_pred)
        #                     y_pred_prob_ls.extend(y_pred_prob)
        #                 else:
        #                     y_true_ls.append(y.numpy())
        #                     y_pred_ls.extend(y_pred)
        #                     y_pred_prob_ls.extend(y_pred_prob)
        #                 break
        #             else:
        #                 program = next_program
        #                 program_str = next_program_str
        #                 outbound_mask_ls = next_outbound_mask_ls
        #                 all_other_pats_ls = next_all_other_pats_ls
        #         if not self.multilabel:
        #             y_true_array = np.array(y_true_ls, dtype=float)
        #             y_pred_array = np.array(y_pred_ls, dtype=float)
        #             y_pred_prob_array = np.array(y_pred_prob_ls, dtype=float)
        #             # y_pred_prob_array = np.concatenate(y_pred_prob_ls, axis = 0)
        #             y_pred_array[y_pred_array < 0] = 0.5
        #             y_pred_prob_array[y_pred_prob_array < 0] = 0.5
        #             if np.sum(y_pred_array == 1) <= 0 or np.sum(y_true_array == 1) <= 0:
        #                 auc_score_2 = 0
        #             else:
        #                 auc_score_2 = roc_auc_score(y_true_array.reshape(-1), y_pred_prob_array.reshape(-1))
        #             success_rate = (success / len(y_pred_array)) * 100.00
        #             avg_loss = sum_loss/len(y_pred_array)
        #             desc = f"[Test Epoch {epoch}] Avg Loss: {avg_loss}, Success: {success}/{len(y_pred_array)} ({success_rate:.2f}%), auc score:{auc_score_2}"
        #             iterator.set_description(desc)
        #         else:
        #             y_true_array = np.concatenate(y_true_ls)
        #             y_pred_array = np.stack(y_pred_ls)
        #             y_pred_prob_array = np.stack(y_pred_prob_ls)
        #             # y_pred_prob_array = np.concatenate(y_pred_prob_ls, axis = 0)
        #             # y_pred_array[y_pred_array < 0] = 0.5
        #             y_pred_prob_array[y_pred_prob_array < 0] = 0.5
        #             # if np.sum(y_pred_array == 1) <= 0 or np.sum(y_true_array == 1) <= 0:
        #             #     auc_score_2 = 0
        #             # else:
        #             selected_label_ids = (np.mean(y_true_array, axis=0) > 0)
        #             try:
        #                 auc_score_2 = roc_auc_score(y_true_array[:,selected_label_ids], y_pred_prob_array[:,selected_label_ids], average=None)
        #             except ValueError:
        #                 auc_score_2 = np.zeros(y_true_array[selected_label_ids].shape[-1])
        #             # success_rate = (success / len(y_pred_array)) * 100.00
        #             success_rate = np.mean(y_true_array == y_pred_array)*100
        #             avg_loss = sum_loss/len(y_pred_array)
        #             # desc = f"[Test Epoch {epoch}] Avg Loss: {avg_loss}, Success: ({success_rate:.2f}%), auc score list:{auc_score_2.tolist()}, auc score mean:{np.mean(auc_score_2)}"
        #             desc = f"[Test Epoch {epoch}] Avg Loss: {avg_loss}, Success: ({success_rate:.2f}%), auc score mean:{np.mean(auc_score_2)}"
        #             iterator.set_description(desc)
        # if self.is_log:
        #     self.logger.log(level=logging.DEBUG, msg = desc)
        

        # additional_score_str = ""
        # full_y_pred_prob_array = np.stack([1 - y_pred_prob_array.reshape(-1), y_pred_prob_array.reshape(-1)], axis=1)
        # for metric_name in metrics_maps:
        #     curr_score = metrics_maps[metric_name](y_true_array.reshape(-1),full_y_pred_prob_array)
        #     additional_score_str += metric_name + ": " + str(curr_score) + " "
        # print(additional_score_str)
        # if self.is_log:
        #     self.logger.log(level=logging.DEBUG, msg = additional_score_str)
        # Print information
        
        # if exp_y_pred_arr is not None:
        #     nonzero_ids = np.nonzero(exp_y_pred_arr != y_pred_array)
        #     print(nonzero_ids[0])
        
        # if self.rl_algorithm == "dqn":
        self.dqn.policy_net.train()
        self.dqn.target_net.train()
        # else:
        #     self.dqn.actor.train()
        #     self.dqn.critic.train()

        # if self.is_log:
        #     full_generated_program_ls, full_program_str_ls, full_label_ls = self.concatenate_program_across_samples(generated_program_ls, generated_program_str_ls, program_label_ls)
        #     self.cluster_programs(full_generated_program_ls, full_program_str_ls,full_label_ls)

    def run(self):
        # exp_pred_array = self.test_epoch(0)
        # train_loader = DataLoader(self.train_dataset, batch_size=self.batch_size, collate_fn = EHRDataset.collate_fn, shuffle=True, drop_last=True)
        # if self.valid_dataset is not None:
        #     valid_loader = DataLoader(self.valid_dataset, batch_size=self.batch_size, collate_fn = EHRDataset.collate_fn, shuffle=False, drop_last=False)
        # test_loader = DataLoader(self.test_dataset, batch_size=self.batch_size, collate_fn = EHRDataset.collate_fn, shuffle=False, drop_last=False)
        train_loader     = DataLoader(dataset=self.train_dataset, collate_fn=data_utils.custom_collate_fn_medical_rl, shuffle=True, batch_size=32,num_workers=2)
        valid_loader = DataLoader(dataset=self.valid_dataset, collate_fn=data_utils.custom_collate_fn_medical_rl, shuffle=False, batch_size=32,num_workers=1)
        test_loader = DataLoader(dataset=self.test_dataset, collate_fn=data_utils.custom_collate_fn_medical_rl, shuffle=False, batch_size=32,num_workers=1)
        if self.is_log:
            # self.test_epoch_ls(valid_loader, 0, feat_embedding=self.test_feat_embeddings)
            self.test_epoch_ls(test_loader, 0, feat_embedding=self.test_feat_embeddings)
            exit(1)    
        # if self.valid_dataset is not None:
        # if self.rl_algorithm == "dqn":
        self.test_epoch_ls(valid_loader, 0, feat_embedding=self.test_feat_embeddings)
        # self.test_epoch_ls(test_loader, 0, feat_embedding=self.test_feat_embeddings)
        # if self.rl_algorithm == "dqn":
        #     torch.save(self.dqn.policy_net.state_dict(), os.path.join(self.work_dir, "policy_net_" + str(0)))
        #     torch.save(self.dqn.target_net.state_dict(), os.path.join(self.work_dir, "target_net_" + str(0)))
        #     # torch.save(self.dqn.memory, os.path.join(self.work_dir, "memory"))
        # else:
        #     torch.save(self.dqn.actor.state_dict(), os.path.join(self.work_dir, "actor_" + str(0)))
        #     torch.save(self.dqn.critic.state_dict(), os.path.join(self.work_dir, "critic_" + str(0)))
        # train_loader = DataLoader(self.train_dataset, batch_size=self.batch_size, collate_fn = EHRDataset.collate_fn, shuffle=False, drop_last=False)
        # with torch.autograd.set_detect_anomaly(True):
        for i in range(1, self.epochs + 1):
            self.train_epoch(i, train_loader)
            torch.save(self.dqn.policy_net.state_dict(), os.path.join(self.work_dir, "policy_net_" + str(i)))
            torch.save(self.dqn.target_net.state_dict(), os.path.join(self.work_dir, "target_net_" + str(i)))
                # torch.save(self.dqn.memory, os.path.join(self.work_dir, "memory"))
            # self.test_epoch(i)
            if self.valid_dataset is not None:
                self.test_epoch_ls(valid_loader, i, feat_embedding=self.valid_feat_embeddings)    
            self.test_epoch_ls(test_loader, i, feat_embedding=self.test_feat_embeddings)
            torch.cuda.empty_cache() 
            gc.collect()
            self.dqn.update_target()
            # self.test_epoch_ls(test_loader, i)
