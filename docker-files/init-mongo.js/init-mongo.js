// init-mongo.js
// Runs once on first container start to set up app user & collection

db = db.getSiblingDB("mydb");

db.createUser({
  user: "appuser",
  pwd: "apppassword",
  roles: [{ role: "readWrite", db: "mydb" }],
});

db.createCollection("jobs");

print("✅  MongoDB initialized: database 'mydb', user 'appuser', collection 'jobs' created.");
