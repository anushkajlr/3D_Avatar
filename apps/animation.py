import argparse
import os

import numpy as np
import torch
from tqdm import tqdm

from lib.net.geometry import rotation_matrix_to_angle_axis
from lib.smplx.lbs import general_lbs
import joblib

# loading cfg file
parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name", type=str, default="")
parser.add_argument("-m", "--motion", type=str, default="rasputin_smplx")
parser.add_argument("-g", "--gpu", type=int, default=0)
args = parser.parse_args()

device = torch.device(f"cuda:{args.gpu}")

econ_dict = torch.load(f"./results/econ/cache/{args.name}/econ.pt")
smplx_pkl = joblib.load(f"./examples/motions/{args.motion}.pkl")
# smplx_pose_mat = torch.tensor(smplx_pkl['pred_thetas'])
# print("taking a look as shape of theta parameters")
# print(smplx_pose_mat.shape)
# smplx_transl = smplx_pkl['transl']
# smplx_pose = rotation_matrix_to_angle_axis(smplx_pose_mat.view(-1, 3, 3)).view(-1, 55, 3)
smplx_pose = smplx_pkl[1]['joints3d']
x = []
for i in range(len(smplx_pose)):
    x.append(np.vstack([smplx_pose[i],np.zeros((6, 3))]))
smplx_pose = torch.tensor(np.array(x)).float()
# print("taking a look at shape of smplx_pose")
# print(smplx_pose.shape)
smplx_pose[:, 23:23 + 2] *= 0.0    # remove the pose of eyes 
n_start = 0
# n_end = 100 * 25
n_end = smplx_pose.shape[0]
n_step = 1

output_dir = f"./results/econ/seq"
os.makedirs(output_dir, exist_ok=True)

motion_output = {"v_seq": [], "f": None, "normal": None, "rgb": None}

for oid, fid in enumerate(tqdm(range(n_start, n_end, n_step))):
    posed_econ_verts, _ = general_lbs(
        pose=smplx_pose.reshape(-1, 55 * 3)[fid:fid + 1].to(device),
        v_template=econ_dict["v_template"].to(device),
        posedirs=econ_dict["posedirs"].to(device),
        J_regressor=econ_dict["J_regressor"].to(device),
        parents=econ_dict["parents"].to(device),
        lbs_weights=econ_dict["lbs_weights"].to(device),
    )
    smplx_verts = posed_econ_verts[0].float().detach().cpu().numpy()
    trans_scale = np.array([1.0, 0.1, 0.1])    # to mitigate z-axis jittering
    #+ smplx_transl[fid] * trans_scale
    motion_output["v_seq"].append((smplx_verts).astype(
        np.float32
    ))

motion_output["v_seq"] = np.stack(motion_output["v_seq"], axis=0)
motion_output["f"] = econ_dict["faces"].astype(np.uint32)
motion_output["normal"] = econ_dict["final_normal"].astype(np.float32)
motion_output["rgb"] = econ_dict["final_rgb"].astype(np.float32)

np.savez_compressed(f"{output_dir}/{args.name}_motion.npz", **motion_output)