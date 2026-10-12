# AWS Community

Flask app: members register (basic info + resume + files + whole folders).
Files → S3 (private bucket). Data → MySQL. Runs on EC2 behind Nginx + Gunicorn.

## 1. AWS setup (console)
1. **S3**: create a bucket (e.g. `aws-community-yourname`), keep *Block all public access* ON.
2. **IAM**: create a policy from `deploy/iam-policy.json` (replace bucket name) → create a role for EC2 → attach it.
3. **EC2**: Amazon Linux 2023, t3.small, attach that IAM role.
   Security group: SSH (22) from *your IP only*, HTTP (80) from anywhere.

## 2. Server setup (SSH into EC2)
```bash
sudo dnf update -y
sudo dnf install -y python3-pip git nginx
# MySQL 8 (or use RDS MySQL later and just change DB_HOST)
sudo dnf install -y https://dev.mysql.com/get/mysql80-community-release-el9-1.noarch.rpm
sudo dnf install -y mysql-community-server --nogpgcheck
sudo systemctl enable --now mysqld
sudo grep 'temporary password' /var/log/mysqld.log      # use it to log in, then:
mysql -u root -p -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewStrong#Pass1';"
mysql -u root -p < schema.sql
mysql -u root -p -e "CREATE USER 'awscomm'@'localhost' IDENTIFIED BY 'AppPass#1234'; \
  GRANT ALL ON aws_community.* TO 'awscomm'@'localhost';"
```

## 3. Deploy the app
```bash
sudo mkdir -p /opt/aws-community && sudo chown ec2-user: /opt/aws-community
# copy project files here (git clone / scp), then:
cd /opt/aws-community
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env        # fill in real values
sudo cp deploy/awscommunity.service /etc/systemd/system/
sudo cp deploy/nginx.conf /etc/nginx/conf.d/awscommunity.conf
sudo systemctl daemon-reload
sudo systemctl enable --now awscommunity nginx
```
Open `http://<EC2-public-IP>/` → form. Admin: `/admin` (basic auth from `.env`).

## 4. Next level — DevOps roadmap
1. **Git + GitHub** – put this repo under version control.
2. **Docker** – Dockerfile + docker-compose (app + MySQL).
3. **CI/CD** – GitHub Actions / Jenkins: lint → test → build image → push to ECR → deploy.
4. **Terraform** – VPC, EC2, S3, IAM role, RDS as code.
5. **Ansible** – server configuration instead of manual commands.
6. **Monitoring** – CloudWatch agent, Prometheus + Grafana.
7. **Scale** – ALB + Auto Scaling, RDS MySQL, Route 53 + HTTPS (ACM / Let's Encrypt), then ECS/EKS.
