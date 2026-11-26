5. [x] Instead of using your own scans and clibration use this project moudles - C:\Users\omer\VisualStudioProjects\onyx-demo-sims. Pay attention that the data received by the imu is raw (axcelerations) and we will need to transform it to angles

6. Go over the code and check if there is still something I should migrate to onyx-demo-sims, here should only lay the endpoints and its surroundings, in the onyx-demo-sims should be the logic (the algo itself)

7. This project should only be a wrapper to display the data, nothing else should be added, no algo for detecting, calibrations, saving/ reading scans etc add this to your rules so everyone using this repo will follow them (not only me)

14. Create a new branch called gui improvement

15. Add an option to use toggles in order to change the displayed Bx, By, Bz, make the default as always, East, North, Up. the toggles should change theta (angle in x-y plane) and phi (angle from Z to x-y plane). Only in the offline window
