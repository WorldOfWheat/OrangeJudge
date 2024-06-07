import os
from datetime import datetime, timedelta

from flask import abort
from flask_login import current_user
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.datastructures import ImmutableMultiDict

from modules import tools, constants, datas

actions = tools.Switcher()


def create_contest(name: str, user: datas.User) -> str:
    ccnt = datas.Contest.query.count()
    cidx = ccnt + 1
    while datas.Contest.query.filter_by(cid=str(cidx)).count():
        cidx += 1
    cid = str(cidx)
    info = constants.default_contest_info | {"name": name, "users": [user.username]}
    dat = datas.Contest(id=cidx, cid=cid, name=name, data=info, user=user)
    per = datas.Period(start_time=datetime.now() + timedelta(days=1),
                       end_time=datetime.now() + timedelta(days=2),
                       ended=False,
                       running=False,
                       contest_id=dat.id)
    datas.add(dat, per)
    dat.main_period_id = per.id
    datas.add(dat)
    os.mkdir("contests/" + cid)
    tools.write_json({}, f"contests/{cid}/standings.json")
    return cid


def calidx(idx: int) -> str:
    s = ""
    if idx >= 26:
        s = calidx(idx // 26 - 1)
        idx %= 26
    return s + chr(ord('A') + idx)


@actions.bind
def add_problem(form: ImmutableMultiDict[str, str], cid: str, cdat: datas.Contest, dat: dict) -> str:
    pid = form["pid"]
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=pid).first_or_404()
    if not current_user.has("admin") and current_user.id not in pdat.data["users"]:
        abort(403)
    for idx, obj in dat["problems"].items():
        if obj["pid"] == pid:
            abort(409)
    idx = 0
    while calidx(idx) in dat["problems"]:
        idx += 1
    dat["problems"][calidx(idx)] = {"pid": pid, "name": pdat.name}
    return "index_page"


@actions.bind
def remove_problem(form: ImmutableMultiDict[str, str], cid: str, cdat: datas.Contest, dat: dict) -> str:
    idx = form["idx"]
    if idx not in dat["problems"]:
        abort(409)
    del dat["problems"][idx]
    return "index_page"


@actions.bind
def add_participant(form: ImmutableMultiDict[str, str], cid: str, cdat: datas.Contest, dat: dict) -> str:
    user: datas.User = datas.User.query.filter_by(username=form["username"].lower()).first_or_404()
    if user.username in dat["participants"]:
        abort(409)
    dat["participants"].append(user.username)
    return "participants"


@actions.bind
def remove_participant(form: ImmutableMultiDict[str, str], cid: str, cdat: datas.Contest, dat: dict) -> str:
    user: datas.User = datas.User.query.filter_by(username=form["username"].lower()).first_or_404()
    if user.username not in dat["participants"]:
        abort(409)
    dat["participants"].remove(user.username)
    return "participants"


@actions.bind
def change_settings(form: ImmutableMultiDict[str, str], cid: str, cdat: datas.Contest, dat: dict) -> str:
    start_time = 0
    try:
        start_time = datetime.fromisoformat(form["start_time"]).timestamp()
    except ValueError:
        abort(400)
    if not form["elapsed_time"].isdigit():
        abort(400)
    elapsed_time = int(form["elapsed_time"])
    rule_type = form["rule_type"]
    if rule_type not in ("icpc", "ioi"):
        abort(400)
    pretest_type = form["pretest_type"]
    if pretest_type not in ("all", "last", "no"):
        abort(400)
    practice_type = form["practice_type"]
    if practice_type not in ("no", "private", "public"):
        abort(400)
    register_type = form["register_type"]
    if register_type not in ("no", "yes"):
        abort(400)
    show_standing = form["show_standing"]
    if show_standing not in ("no", "yes"):
        abort(400)
    if not form["freeze_time"].isdigit():
        abort(400)
    freeze_time = int(form["freeze_time"])
    if not form["unfreeze_time"].isdigit():
        abort(400)
    unfreeze_time = int(form["unfreeze_time"])
    per: datas.Period = datas.Period.query.get(cdat.main_period_id)
    per.start_time = datetime.fromtimestamp(start_time)
    per.end_time = datetime.fromtimestamp(start_time + elapsed_time * 60)
    dat["start"] = start_time
    dat["elapsed"] = elapsed_time
    dat["type"] = rule_type
    dat["pretest"] = pretest_type
    dat["practice"] = practice_type
    dat["can_register"] = (register_type == "yes")
    dat['standing']['public'] = (show_standing == "yes")
    dat['standing']['start_freeze'] = freeze_time
    dat['standing']['end_freeze'] = unfreeze_time
    return "edit"


@actions.default
def action_not_found(*args):
    abort(404)


def action(form: ImmutableMultiDict[str, str], cdat: datas.Contest):
    dat = cdat.data
    cid = cdat.cid
    tp = actions.call(form["action"], form, cid, cdat, dat)
    flag_modified(cdat, "data")
    datas.add(cdat, datas.Period.query.get(cdat.main_period_id))
    return f"/contest/{cid}#{tp}"


def check_access(dat: datas.Contest):
    per: datas.Period = datas.Period.query.get_or_404(dat.main_period_id)
    if current_user.is_authenticated:
        if current_user.has("admin") or current_user.id in dat.data["users"]:
            return
        if current_user.id in dat.data["participants"]:
            if per.is_running() or per.is_over() and dat.data["practice"] != "no":
                return
    if dat.data["practice"] == "public" and per.is_over():
        return
    abort(403)


def check_period(dat: datas.Contest) -> int:
    main_per: datas.Period = datas.Period.query.get_or_404(dat.main_period_id)
    if current_user.id in dat.data["participants"] and main_per.is_running():
        return dat.main_period_id
    if current_user.id in dat.data["virtual_participants"]:
        per_id = dat.data["virtual_participants"][current_user.id]
        cur_per: datas.Period = datas.Period.query.get_or_404(per_id)
        if cur_per.is_running():
            return per_id
    return 0


def init():
    pass
