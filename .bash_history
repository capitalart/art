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
