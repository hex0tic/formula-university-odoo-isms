REGISTRAR_GROUP = "campus_university.group_campus_registrar"
LECTURER_GROUP = "campus_university.group_campus_lecturer"


def is_registrar(env):
    """Superuser mode or the registrar group. Never derived from context flags."""
    return env.su or env.user.has_group(REGISTRAR_GROUP)
