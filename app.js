const express = require("express");
const session = require("express-session");
const Auth = require("./routers/auth");
const Chat = require('./routers/chat')
const {checkToken} = require('./utils/validation')
require("dotenv").config();

host = process.env.HOST

const app = express();
const port = 3000;

app.set("view engine", "ejs");
app.set("views", __dirname + "/views");
app.use(express.static('public'));
app.use(
  session({
    secret: process.env.PASS_KEY,
    resave: false,
    saveUninitialized: true,
  })
);

app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.use("/", Auth);
app.use("/", Chat);
app.get("/", checkToken, async (req, res) => {
  res.render("index");
});


app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
