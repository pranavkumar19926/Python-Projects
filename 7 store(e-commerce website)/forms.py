from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FloatField, IntegerField, BooleanField, FileField ,StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange, InputRequired, Length

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    is_seller = BooleanField("Register as Seller (create seller account)")
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    username = StringField("Username or Email", validators=[DataRequired(), Length(min=3, max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class ProductForm(FlaskForm):
    name = StringField("Product Name", validators=[DataRequired(), Length(max=255)])
    slug = StringField("Slug (optional)", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0)])
    image = FileField("Product Image (jpg/png/gif)", validators=[Optional()])
    submit = SubmitField("Save Product")

class SimpleSearchForm(FlaskForm):
    q = StringField("Search", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Search")
class AddressForm(FlaskForm):
    full_name = StringField("Full Name", validators=[InputRequired()])
    phone = StringField("Phone Number", validators=[InputRequired(), Length(min=10, max=10)])
    line1 = StringField("Address Line 1", validators=[InputRequired()])
    line2 = StringField("Address Line 2")
    city = StringField("City", validators=[InputRequired()])
    state = StringField("State", validators=[InputRequired()])
    pincode = StringField("Pincode", validators=[InputRequired(), Length(min=6, max=6)])
    submit = SubmitField("Save Address")