set -euo pipefail

# cleaning
k3d cluster delete inkwell

# build docker
docker build -t inkwell-web:0.1.0 .

# create cluster
k3d cluster create inkwell --agents 2 -p "8080:80@loadbalancer"
kubectl config current-context        # powinno być: k3d-inkwell

# move image to cluster
k3d image import inkwell-web:0.1.0 -c inkwell

# create namespace and database
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/postgres/
kubectl rollout status statefulset/postgres -n inkwell --timeout=180s
kubectl wait --for=condition=ready pod/postgres-0 -n inkwell --timeout=120s

# create redis
kubectl apply -f k8s/redis/
kubectl rollout status deployment/redis -n inkwell --timeout=120s
kubectl wait --for=condition=available deploy/redis -n inkwell --timeout=60s

# configuration i migrations
kubectl apply -f k8s/web/configmap.yml -f k8s/web/secret.yml
kubectl apply -f k8s/web/job-migrate.yml
kubectl wait --for=condition=complete job/migrate -n inkwell --timeout=120s

# application
kubectl apply -f k8s/web/deployment.yml -f k8s/web/service.yml -f k8s/web/ingress.yml
kubectl rollout status deployment/web -n inkwell --timeout=180s
kubectl wait --for=condition=available deploy/web -n inkwell --timeout=120s

# create superuser
# kubectl exec -it -n inkwell deploy/web -- python manage.py createsuperuser

# restore database
kubectl exec -i -n inkwell postgres-0 -- pg_restore -U postgres -d inkwell --clean --if-exists < inkwell.dump

# check
kubectl get pods -n inkwell