from django.db import models

class MedService(models.Model):
    """
        Has information regarding health clinic
        Name, Location, Email, Number, Boolean if they take appointments or not
    """
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    email = models.EmailField(max_length=200)
    number = models.CharField(max_length=200) # has to be char because we have dashes (-) but not sure maybe? idk
    appointments_required = models.BooleanField(default=True) # defaulted to true if we do not know

    class Meta: # default ordering by name
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name", "location"], name="unique_name_location")]

    def __str__(self):
        return f"{self.name} ({self.location})"


class User(models.Model):
    """
    Has information regarding the actual user
    Username, email, password, access tokens
    For user accounts
    """

    username = models.CharField(max_length=200, unique=True) # true so people can't have same username
    email = models.EmailField(max_length=200, unique=True) # true so people can't have same emails as well (unique users)
    password = models.CharField(max_length=200)
    access_token = models.CharField(max_length=200, unique=True) # each access token is different and constantly gets updated

    class Meta:
        ordering = ["username"] # default order everything by username

    def __str__(self):
        return f"{self.username}"

class History(models.Model):
    """
    Has recorded chat history that user creates so they can look back on
    """
    user = models.ForeignKey(User, related_name="history", on_delete=models.CASCADE) # every user has diff chat history therefore we use foreign keys
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True) # date and time that chat was made

    class Meta:
        ordering = ["-date"] # default odering by date

    def __str__(self):
        return f"{self.user.username} @ {self.date}"