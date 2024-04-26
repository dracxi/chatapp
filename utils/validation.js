const checkToken = (req, res, next) => {
    const token = req.session.token;
    if (!token) {
      return res.redirect("/login");
    }
    next();
  };

module.exports = {
    checkToken
};