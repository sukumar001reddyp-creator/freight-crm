from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length


class PortalLoginForm(FlaskForm):
    username = StringField(
        "Username / Email",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )

    submit = SubmitField("Login")


class ShipmentSearchForm(FlaskForm):
    shipment_reference = StringField(
        "Shipment Reference",
        validators=[
            DataRequired(),
            Length(max=100)
        ]
    )

    submit = SubmitField("Track Shipment")


class SupportRequestForm(FlaskForm):
    subject = StringField(
        "Subject",
        validators=[
            DataRequired(),
            Length(max=200)
        ]
    )

    message = TextAreaField(
        "Message",
        validators=[
            DataRequired(),
            Length(max=5000)
        ]
    )

    submit = SubmitField("Send Request")