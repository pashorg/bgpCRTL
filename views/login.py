from django.contrib.auth import authenticate, login as auth_login
from django.shortcuts import render, redirect


# Log in using Django services
def login(request):
    if request.POST.get('submit', False):
        username = request.POST['username']
        password = request.POST['password']
        next = request.POST['next']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if next:
                return redirect(next)
            else:
                return redirect('/')
        else:
            return render(request, 'facer/login.html',
                          {
                              'username': username,
                              'next': next,
                              'error': 'Неверное имя пользователя или пароль!'
                          })
    else:
        return render(request, 'facer/login.html', {'next': request.GET.get('next', '/')})
