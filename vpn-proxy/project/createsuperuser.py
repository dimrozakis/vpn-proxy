def main(username='admin', password='admin', email='admin@example.com'):
    from django.contrib.auth.models import User
    try:
        User.objects.get(username=username)
        print "User '%s' already exists." % username
    except User.DoesNotExist:
        print "Creating user '%s' (%s) with password '%s'." % (username, email,
                                                               password)
        User.objects.create_superuser(username, email, password)


if __name__ == '__main__':
    main()
