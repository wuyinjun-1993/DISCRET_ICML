#!/bin/bash
trap ctrl_c INT

cd ../image/

echo $pwd

init_cmd=$1

output_folder=$2

export CUDA_VISIBLE_DEVICES=$3

explanation_type=$4

id_ls=()

for ((i=1; i<=5; i++))
#for i in "${id_ls[@]}";
do
	echo "repeat ihdp iteration $i"
	curr_log_folder=$output_folder
	mkdir -p $curr_log_folder
	curr_log_folder=$curr_log_folder/$i
	mkdir -p $curr_log_folder
#	cmd="python train_tabular_rl.py --epochs 2000 --num_treatments 2 --dataset_name ihdp --batch_size 256 --lr 1e-3 --topk_act 1 --program_max_len 4 --log_folder /data6/wuyinjun/causal_tabular/ihdp/logs/ --model_config configs/configs_ihdp.yaml --method ours --dataset_id $i"
	cmd="$init_cmd --log_folder $curr_log_folder --seed ${i} --explanation_type ${explanation_type}"
	echo $cmd
        $cmd > $output_folder/output_${explanation_type}_log_$i.txt 2>&1

done
