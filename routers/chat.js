const express = require("express");
const session = require("express-session");
const axios = require("axios");
const qs = require("qs");
const { checkToken } = require("../utils/validation");
const router = express.Router();

router.get('/chat/:id',checkToken, (req, res) => {
    const id = req.params.id;
    res.render('chatpage', { id: id });
});

module.exports = router;