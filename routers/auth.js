const express = require("express");
const session = require("express-session");
const axios = require("axios");
const qs = require("qs");
const { checkToken } = require("../utils/validation");
const router = express.Router();

router.get("/login", (req, res) => {
  res.render("login");
});

router.post("/login", async (req, res) => {
  const { username, password } = req.body;
  try {
    const response = await axios.post(
      `${port}://${host}/auth/login`,
      qs.stringify({
        username,
        password,
      }),
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }
    );
    const data = response.data;
    req.session.token = data.token;
    req.session.id = data.id;
    res.redirect("/");
  } catch (error) {
    console.log(error);
    res.redirect("/login?error=1");
  }
});

router.get("/token", checkToken, (req, res) => {
  token = req.session.token;
  id = req.session.id;
  res.json({ token ,id });
});

module.exports = router;
