from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout


# Log out using Django services
def logout(request):
    auth_logout(request)
    return redirect('/login/')
