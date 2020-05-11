#!/bin/bash -x

#### Resource Request: ####
# Cascades has the following hardware:
#   a. 190 32-core, 128 GB Intel Broadwell nodes
#   b.   4 32-core, 512 GB Intel Broadwell nodes with 2 Nvidia K80 GPU
#   c.   2 72-core,   3 TB Intel Broadwell nodes
#   d.  39 24-core, 376 GB Intel Skylake nodes with 2 Nvidia V100 GPU
#
# Resources can be requested by specifying the number of nodes, cores, memory, GPUs, etc
# Examples:
#   Request 4 cores (on any number of nodes)
#   #SBATCH --ntasks=4
#   Request exclusive access to all resources on 2 nodes
#   #SBATCH --nodes=2
#   #SBATCH --exclusive
#   Request 4 cores (on any number of nodes)
#   #SBATCH --ntasks=4
#   Request 2 nodes with 12 tasks running on each
#   #SBATCH --nodes=2
#   #SBATCH --ntasks-per-node=12
#   Request 12 tasks with 20GB memory per core
#   #SBATCH --ntasks=12
#   #SBATCH --mem-per-cpu=20G
#   Request 5 nodes and spread 50 tasks evenly across them
#   #SBATCH --nodes=5
#   #SBATCH --ntasks=50
#   #SBATCH --spread-job
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --mail-type=ALL
#SBATCH --mail-user=sampanna@vt.edu

#### Walltime ####
#SBATCH -t 40:00:00

#### Queue ####
# Queue name. Cascades has five queues:
#   normal_q        for production jobs on all Broadwell nodes
#   largemem_q      for jobs on the two 3TB, 60-core Ivy Bridge servers
#   dev_q           for development/debugging jobs. These jobs must be short but can be large.
#   v100_normal_q   for production jobs on Skylake/V100 nodes
#   v100_dev_q      for development/debugging jobs on Skylake/V100 nodes
#SBATCH -p normal_q
#SBATCH -A waingram_lab

module purge

# Below here enter the commands to start your job. A few examples are provided below.
# Some useful variables set by the job:
#  $SLURM_SUBMIT_DIR   Directory from which the job was submitted
#  $PBS_NODEFILE       File containing list of cores available to the job
#  $PBS_GPUFILE        File containing list of GPUs available to the job
#  $SLURM_JOBID        Job ID (e.g., 107619.master.cluster)
#  $SLURM_NTASKS       Number of cores allocated to the job
# You can run the following (inside a job) to see what environment variables are available:
#  env | grep SLURM
#
# Some useful storage locations (see ARC's Storage documentation for details):
#  $HOME     Home directory. Use for permanent files.
#  $WORK     Work directory. Use for fast I/O.
#  $TMPFS    File system set up in memory for this job. Use for very fast, small I/O
#  $TMPDIR   Local disk (hard drive) space set up for this job

current_timestamp() {
  date +"%Y-%m-%d_%H-%M-%S"
}
ts=$(current_timestamp)

# Change to the directory from which the job was submitted
cd "$WORK"/deepfigures-results || exit
if [ -z ${SLURM_ARRAY_TASK_ID+x} ]; then
  echo "SLURM_ARRAY_TASK_ID is not set. Stopping the job."
  exit
fi

i=$SLURM_ARRAY_TASK_ID

NUM_CPUS=$(lscpu | grep "CPU(s)" | head -1 | awk -F' ' '{print $2}')
NUM_CPUS_TIMES_2=$((NUM_CPUS * 2))

echo "Number of CPUs : $NUM_CPUS"
echo "Number of CPUs times 2 : $NUM_CPUS_TIMES_2"

/home/sampanna/.conda/envs/deepfigures/bin/python /home/sampanna/deepfigures-open/deepfigures/data_generation/training_data_generator.py --file_list_json /home/sampanna/deepfigures-results/files_"$i".json --images_per_zip=500 --zip_save_dir=/work/cascades/sampanna/deepfigures-results/pregenerated_training_data/"$ts"_"$SLURM_JOBID"_"$i" --n_cpu=$NUM_CPUS_TIMES_2

echo "Job ended. Job ID: $SLURM_JOBID . Array ID: $i"

exit
