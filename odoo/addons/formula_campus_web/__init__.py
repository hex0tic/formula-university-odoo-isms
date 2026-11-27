from . import controllers
from . import models


def post_init_hook(env):
    env["formula.public.program"]._match_academic_programs()
