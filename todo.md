5. Create new branch called finishing cleanup

6. Go over the code and check if there is still something I should migrate to onyx-demo-sims, here should only lay the endpoints and its surroundings, in the onyx-demo-sims should be the logic (the algo itself), for example, make sure that the coverting from voltage to nT isn't in this project

7. This project should only be a wrapper to display the data, nothing else should be added, no algo for detecting, calibrations, saving/ reading scans etc add this to your rules so everyone using this repo will follow them (not only me)

14. Create a new branch called gui improvement

15. Add an option to use toggles in order to change the displayed Bx, By, Bz, make the default as always, East, North, Up. the toggles should change theta (angle in x-y plane) and phi (angle from Z to x-y plane). Only in the offline window

16. Create new branch called deal with electromagnetic file

17. fix the file too large error

18. Fix the fact the files are too large
