### Set up the MySQL docker image:  
`docker pull mysql:8.0`
### create the MySQL container:  
`docker run --name mysql-container -e MYSQL_ROOT_PASSWORD=rootpassword -e MYSQL_DATABASE=database -p 3307:3306 -v mysql_data:/var/lib/mysql -d mysql:8.0`  
### Create the database:
```
docker exec -it mysql-container mysql -u root -p
CREATE SCHEMA `database`;
EXIT;
```