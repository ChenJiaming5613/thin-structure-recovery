conda activate gaussian_splatting

cd ~

./fix.sh

cd ~/algos/gaussian_splatting

source_path=/mnt/d/CJM/datasets/
model_path=/mnt/d/CJM/eval_out/3dgs/

scene_path=tandt/truck
python train.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path} -i images -r 1 --iterations 30000
python render.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path}
python metrics.py -m ${model_path}${scene_path}

scene_path=tandt/train
python train.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path} -i images -r 1 --iterations 30000
python render.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path}
python metrics.py -m ${model_path}${scene_path}

scene_path=waymo/cam_0_FRONT
python train.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path} -i images -r 1 --iterations 30000
python render.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path}
python metrics.py -m ${model_path}${scene_path}

scene_path=tanks/courthouse
python train.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path} -i images -r 1 --iterations 30000
python render.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path}
python metrics.py -m ${model_path}${scene_path}

# scene_path=m19/rubble200
# python train.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path} -i images -r 1 --iterations 30000
# python render.py --eval -s ${source_path}${scene_path} -m ${model_path}${scene_path}
# python metrics.py -m ${model_path}${scene_path}
