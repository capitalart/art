source venv/bin/activate
rm -rf .git/rebase-merge
git clean -fd
git status
git checkout main
git restore .bash_history
git checkout main
git add .bash_history
git commit -m "Save changes to .bash_history"
git checkout main
git pull origin main
cd /home
git clone https://github.com/capitalart/ezy.git
cd ezy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # if empty, install basic Flask
pip install flask gunicorn
pip freeze > requirements.txt
cd ..
cd art
ls
bash /home/art/project-toolkit.sh
rclone config
rclone lsd gdrive:
bash /home/art/project-toolkit.sh
ls -l instructions
bash /home/art/project-toolkit.sh
bfg --delete-files '.config/rclone/rclone.conf' --no-blob-protection
bfg --delete-files '.config/rclone.conf' --no-blob-protection
bfg --delete-files 'rclone.conf' --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
bash /home/art/project-toolkit.sh
bfg --delete-files "rclone.conf" --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin main --force
git add .gitignore
git commit
bash /home/art/project-toolkit.sh
git push
bfg --delete-files '.config/rclone/rclone.conf' --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin main --force
git rm --cached .config/rclone/rclone.conf
git commit -m "Remove sensitive file .config/rclone/rclone.conf"
git push origin main
bfg --delete-files 'rclone.conf' --no-blob-protection
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git ls-files | grep .config
git rm --cached .config/jgit/config
git rm --cached .gitconfig
git commit -m "Stop tracking .config/jgit/config and .gitconfig"
git push origin main
git push
git push origin main
git add .gitignore
git commit
git rm --cached .config/jgit/config
git rm --cached .gitconfig
bash /home/art/project-toolkit.sh
ls /etc/systemd/system/
sudo mv /home/art/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gunicorn.service
sudo systemctl start gunicorn
sudo systemctl status gunicorn
pkill gunicorn
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
source venv/bin/activate
sudo journalctl -u gunicorn -f
source venv/bin/activate
sudo nano /etc/systemd/system/gunicorn.service
ls -l /home/art
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
source venv/bin/activate
bash /home/art/project-toolkit.sh
/home/art/venv/bin/gunicorn --workers 4 --bind unix:/home/art/artnarrator.sock --access-logfile /home/art/logs/gunicorn-access.log --error-logfile /home/art/logs/gunicorn-error.log --timeout 120 --graceful-timeout 60 --max-requests 1000 --max-requests-jitter 100 --preload --chdir /home/art
source /home/art/venv/bin/activate
pip install -r /home/art/requirements.txt
rm -f /home/art/artnarrator.sock
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
pkill gunicorn
ps aux | grep gunicorn
kill 1097556
gunicorn app:app
sudo journalctl -u gunicorn -f
pkill gunicorn
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
pkill gunicorn
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
source venv/bin/activate
bash /home/art/project-toolkit.sh
ps aux | grep gunicorn
tail -f /home/art/logs/gunicorn-error.log
source venv/bin/activate
curl --unix-socket /home/art/artnarrator.sock http://localhost/health
curl http://localhost:7777/health
ps aux | grep gunicorn
sudo netstat -tuln | grep 7777
curl http://127.0.0.1:7777/health
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo journalctl -u gunicorn -f
sudo lsof -i :7777
sudo systemctl status gunicorn
curl http://127.0.0.1:7777/health
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
source venv/bin/activate
sudo journalctl -u gunicorn -f
pkill gunicorn
sudo journalctl -u gunicorn -f
curl http://127.0.0.1:7777/health
curl --unix-socket /home/art/artnarrator.sock http://localhost/health
source venv/bin/activate
curl http://127.0.0.1:7777/health
curl --unix-socket /home/art/artnarrator.sock http://localhost/health
sudo netstat -tuln | grep 7777
bash /home/art/project-toolkit.sh
rclone config show
rclone config
bash /home/art/project-toolkit.sh
ulimit -a
ps -u art | grep python
bash /home/art/project-toolkit.sh
gunicorn app:app
ulimit -a
tail -f /home/art/logs/gunicorn-error.log
sudo nano /etc/security/limits.conf
sudo nano /etc/systemd/system.conf
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
chmod +x setup_gunicorn.sh
./setup_gunicorn.sh
curl http://127.0.0.1:7777/health
sudo systemctl status gunicorn
tail -f /home/art/logs/gunicorn-error.log
ps aux | grep gunicorn
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
tail -f /home/art/logs/gunicorn-error.log
sudo journalctl -u gunicorn -f
ulimit -a
sudo systemctl stop gunicorn
/home/art/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:7777 --bind unix:/home/art/artnarrator.sock --access-logfile /home/art/logs/gunicorn-access.log --error-logfile /home/art/logs/gunicorn-error.log
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo nano /etc/security/limits.conf
sudo reboot
ulimit -n  # Check the max number of open files
ulimit -u  # Check the max number of processes
ulimit -n  # Check the max number of open files
ulimit -u  # Check the max number of processes
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo chown -R art:art /home/art/ezy /home/art/linuxbrew /home/art/linuxbrew/.linuxbrew /home/art/robin /home/art/thebigshed /home/art/.gitignore
cd ..
ls
cd ~
cd ..
ls
sudo chown -R art:art /home/ezy /home/linuxbrew /home/robin /home/thebigshed
rm -rf /home/ezy /home/linuxbrew /home/robin /home/thebigshed
ls -l /home/ezy /home/linuxbrew /home/robin /home/thebigshed
sudo rm -rf /home/ezy /home/linuxbrew /home/robin /home/thebigshed
mount | grep '/home/ezy\|/home/linuxbrew\|/home/robin\|/home/thebigshed'
sudo umount /home/ezy /home/linuxbrew /home/robin /home/thebigshed
lsattr /home/ezy /home/linuxbrew /home/robin /home/thebigshed
ls /home
source venv/bin/activate
sudo lsof -i :7777
sudo kill -9 3871 3872 3873
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo lsof -i :7777
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
sudo systemctl status gunicorn
tail -f /home/art/logs/gunicorn-error.log
sudo nano /etc/systemd/system.conf
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
tail -f /home/art/logs/gunicorn-error.log
sudo systemctl stop gunicorn
sudo systemctl disable gunicorn
sudo pip uninstall gunicorn
source venv/bin/activate
sudo pip uninstall gunicorn
which python
pip uninstall gunicorn
pip list
pip install gunicorn
/home/art/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:7777 --bind unix:/home/art/artnarrator.sock --access-logfile /home/art/logs/gunicorn-access.log --error-logfile /home/art/logs/gunicorn-error.log app:app
sudo systemctl status gunicorn
tail -f /home/art/logs/gunicorn/gunicorn-error.log
sudo systemctl enable gunicorn
source venv/bin/activate
tail -f /home/art/logs/gunicorn/gunicorn-error.log
source venv/bin/activate
curl http://127.0.0.1:7777/health
sudo systemctl status gunicorn
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl status gunicorn
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo chown -R art:art /home/art/logs/gunicorn
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
tail -f /home/art/logs/gunicorn/gunicorn-access.log
source venv/bin/activate
bash /home/art/project-toolkit.sh
git pull origin main
git pull --no-rebase
bash /home/art/project-toolkit.sh
source venv/bin/activate
bash /home/art/project-toolkit.sh
source venv/bin/activate bash /home/art/project-toolkit
source venv/bin/activate
bash /home/art/project-toolkit.sh
sudo nano /etc/systemd/system/gunicorn.service
sudo systemctl edit --full gunicorn
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
bash /home/art/project-toolkit.sh
source /home/art/venv/bin/activate
/home/art/venv/bin/python
source /home/art/venv/bin/activate
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
ps aux | grep gunicorn
pkill gunicorn
ps aux | grep gunicorn
pkill gunicorn
ps aux | grep gunicorn
sudo systemctl stop gunicorn
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
source venv/bin/activate
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
chmod +x scripts/test_connections.py
python3 scripts/test_connections.py
bash /home/art/project-toolkit.sh
python3 scripts/test_connections.py
source /home/art/venv/bin/activate
python3 scripts/test_connections.py
sudo systemctl restart gunicorn
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn
sudo chown -R art:art /home/art/logs
sudo systemctl start gunicorn
sudo systemctl stop gunicorn
sudo chown -R art:art /home/art/logs
sudo systemctl stop gunicorn
sudo chown -R art:art /home/art/logs
sudo systemctl restart gunicorn
sudo systemctl stop gunicorn
sudo systemctl restart gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
sudo systemctl status gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
python3 scripts/populate_gdws.py
sudo systemctl restart gunicorn
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl stop gunicorn
sudo systemctl start gunicorn
sudo systemctl stop gunicorn && sudo systemctl start gunicorn
pip install imagehash
sudo systemctl stop gunicorn && sudo systemctl start gunicorn
sudo systemctl stop gunicorn
sudo chown -R art:art /home/art/logs
sudo systemctl restart gunicorn
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn
sudo systemctl restart gunicorn
sudo journalctl -u gunicorn -f
source venv/bin/activate
bash /home/art/project-toolkit.sh
git rev-list --objects --all | grep 2a2f9c4f352145d48b18da40b0ef7e1e1633d587
git filter-repo --path .env --invert-paths
sudo apt update
sudo apt install git-filter-repo
git filter-repo --help
git filter-repo --path .env --invert-paths
git filter-repo --path .env --invert-paths --force
git push --force
git remote add origin https://github.com/capitalart/art.git
git remote -v
git push --force origin main
source venv/bin/activate
bash /home/art/project-toolkit.sh
source venv/bin/activate
python3 scripts/test_sellbrite_add_listing.py --dry-run
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn && sudo systemctl start gunicorn
sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
bash /home/art/project-toolkit.sh
sudo systemctl status gunicorn
ps aux | grep gunicorn
sudo systemctl stop gunicorn
ps aux | grep gunicorn
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
pkill gunicorn
ps aux | grep gunicorn
pkill gunicorn
ps aux | grep gunicorn
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
sudo systemctl stop gunicorn 
pkill gunicorn
ps aux | grep gunicorn
ps aux | grep 'gunicorn: master'
sudo kill -9 85319
sudo systemctl status gunicorn
sudo systemctl restart gunicorn
ps aux | grep 'gunicorn: master'
sudo kill -9 87210
pkill gunicorn
sudo systemctl stop gunicorn
ps aux | grep gunicorn
sudo systemctl start gunicorn
sudo journalctl -u gunicorn.service --since "5 minutes ago"
sudo journalctl -u gunicorn.service --since "5 minutes ago" --no-pager
sudo systemctl stop gunicorn.service
source /home/art/venv/bin/activate
gunicorn --workers 1 --bind 127.0.0.1:8000 app:app
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo systemctl stop gunicorn.service
deactivate
source /home/art/venv/bin/activate
gunicorn --config /home/art/gunicorn.conf.py app:app
source /home/art/venv/bin/activate
python3 scripts/run_coordinate_generator.py
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
sudo journalctl -u gunicorn -f
mkdir -p /home/art/logs/gunicorn/
sudo systemctl restart gunicorn.service
source /home/art/venv/bin/activate
sudo systemctl restart gunicorn.service
sudo systemctl status gunicorn.service
sudo systemctl restart gunicorn.service
sudo systemctl status gunicorn.service
sudo journalctl -u gunicorn.service -n 100 --no-pager
cat /home/art/logs/gunicorn/gunicorn-error.log
gunicorn app:app
ps aux | grep gunicorn
cat /home/art/logs/gunicorn/gunicorn-error.log
sudo systemctl status gunicorn
cat /home/art/logs/gunicorn/gunicorn-error.log
bash /home/art/project-toolkit.sh
git pull
bash /home/art/project-toolkit.sh
0
deactivate
source venv/bin/activate
sudo systemctl stop gunicorn
sudo systemctl restart gunicorn
sudo systemctl status gunicorn
sudo systemctl status gunicorn.service
cat /home/art/logs/composites-workflow.log
sudo touch /home/art/logs/composites-workflow.log
sudo chown art:art /home/art/logs
sudo chown art:art /home/art/logs/composites-workflow.log
sudo systemctl restart gunicorn
bash /home/art/project-toolkit.sh
0
bash /home/art/project-toolkit.sh
git pull
git pull origin main
git branch --set-upstream-to=origin/main main
git pull origin codex/fix-dynamic-category-dropdown-on-edit-page
git fetch origin
git checkout main
git reset --hard origin/main
git pull
bash /home/art/project-toolkit.sh
git stash push -m "Temporary save before pull"
git pull
git stash pop
bash /home/art/project-toolkit.sh
source /home/art/venv/bin/activate
sudo journalctl -u gunicorn -f
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
./code-stacker.sh
bash /home/art/project-toolkit.sh
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
bash /home/art/project-toolkit.sh
chmod 755 scripts/sellbrite_csv_export.py
chmod 755 scripts/test_sellbrite_add_listing.py
chmod 644 routes/export_routes.py
chmod 644 routes/sellbrite_export.py
chmod 644 routes/sellbrite_service.py
chmod 644 templates/sellbrite_management.html
chmod 644 templates/sellbrite_exports.html
chmod 644 templates/sellbrite_csv_preview.html
chmod 644 templates/sellbrite_log.html
chmod 775 outputs/sellbrite
chmod 644 routes/sellbrite_export.py
chmod 644 routes/sellbrite_service.py
chmod 644 routes/export_routes.py
chmod 644 templates/sellbrite_management.html
chmod 644 templates/sellbrite_sync_preview.html
chmod 644 templates/main.html
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
sudo systemctl stop gunicorn && sudo systemctl start gunicorn && sudo journalctl -u gunicorn -f
source /home/art/venv/bin/activate
bash /home/art/project-toolkit.sh
python3 generate_folder_tree.py
./project-toolkit.sh
pip install -r requirements.txt
./project-toolkit.sh
./code-stacker
./code-stacker.sh
./project-toolkit.sh
