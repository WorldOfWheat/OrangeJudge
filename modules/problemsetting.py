import json
import os
import shutil
import subprocess
import time
import uuid
from time import sleep

from flask import Response, abort, jsonify, render_template, request, redirect, send_file
from pyzipper.zipfile_aes import AESZipInfo
from werkzeug.datastructures import ImmutableMultiDict, MultiDict
from werkzeug.utils import secure_filename

from modules import executing, tools
from modules.locks import locks
from modules.createhtml import run_markdown, parse
from multiprocessing import Queue, Process
from pyzipper import AESZipFile

from modules.tools import J

worker_queue = Queue()

ignores = """/waiting
testcases/gen/
testcases_gen/"""

root_folder = os.getcwd()
background_actions = tools.Switcher()
actions = tools.Switcher()


def init():
    global root_folder
    root_folder = os.path.abspath(os.getcwd())
    Process(target=runner).start()


def system(s, cwd: str):
    cwd = os.path.abspath(cwd)
    print(f"system command in {cwd!r}:", s)
    subprocess.call(s, shell=True, cwd=cwd)


def getout(s, cwd: str) -> str:
    cwd = os.path.abspath(cwd)
    print(f"get stdout for system command in {cwd!r}:", s)
    ret = subprocess.run(s, shell=True, cwd=cwd, capture_output=True).stdout.decode("utf-8")
    print(ret)
    return ret


def create_problem(name, user):
    with locks["create_problem"]:
        with open("data/problem_count") as f:
            pid = int(f.read())
        pid = str(pid + 1)
        with open("data/problem_count", "w") as f:
            f.write(pid)
    os.mkdir("preparing_problems/" + pid)
    worker_queue.put({"action": "init_problem", "pid": pid, "name": name, "user": user})
    return pid


def making_dir(path: str):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, ".gitkeep"), "w"):
        pass


@background_actions.bind
def init_problem(pid, name, user):
    path = "preparing_problems/" + pid
    system(f"sudo dd if=/dev/zero of={pid}.img bs=1G count=1", "preparing_problems")
    system(f"sudo mkfs.ext4 {pid}.img", "preparing_problems")
    try:
        os.remove(path + "/waiting")
    except FileNotFoundError:
        pass
    system(f"sudo mount -o loop {pid}.img ./{pid}", "preparing_problems")
    tools.write("建立題目", path, "waiting")
    try:
        making_dir(path + "/testcases")
        making_dir(path + "/file")
        making_dir(path + "/public_file")
    except FileExistsError:
        pass
    # print(creater)
    # cmd = creater.format(pid=pid)
    # system(cmd)
    info = {"name": name, "timelimit": "1000", "memorylimit": "256", "testcases": [], "users": [user], "statement":
        {"main": "", "input": "", "output": "", "score": ""}, "files": [], "checker_source": ["default", "wcmp.cpp"]}
    tools.write_json(info, path + "/info.json")
    shutil.copy("testlib/checkers/wcmp", path)
    # system("git init", path)
    # system("git add -A", path)
    # system("git commit -m '初始版本'", path)
    # system("git branch -m main", path)
    # system(f"git clone {os.path.abspath(path)} {pid}", os.path.abspath("problems"))
    # system_orange(f'git remote add origin git@orangejudge-github:OrangeJudgeOrg/Problem-{pid}.git')
    # system_orange(f'git push --set-upstream origin main')
    try:
        os.remove(path + "/waiting")
    except FileNotFoundError:
        pass


@background_actions.bind
def compile_checker(pid):
    path = "preparing_problems" | J | pid
    env = executing.Environment()
    dat = tools.read_json(path, "info.json")
    filepath = ("testlib/checkers" if dat["checker_source"][0] == "default" else f"{path}/file") | J | \
               dat["checker_source"][1]
    file = env.send_file(filepath)
    env.send_file("testlib/testlib.h")
    lang_type = "C++17"
    if dat["checker_source"][0] == "my":
        for o in dat["files"]:
            if o["name"] == dat["checker_source"][1]:
                lang_type = o["type"]
    lang = executing.langs[lang_type]
    outfile, ce_msg = lang.compile(file, env)
    if ce_msg:
        return
    outpath = path | J | os.path.basename(outfile)
    env.get_file(outpath)
    dat["checker"] = [os.path.basename(outfile), "C++17"]
    tools.write_json(dat, path, "info.json")


@background_actions.bind
def generate_testcase(pid):
    path = "preparing_problems/" + pid
    dat = tools.read_json(path, "info.json")
    env = executing.Environment()
    if "gen_msg" not in dat:
        return
    filepath = path + "/file/" + dat["gen_msg"]["generator"]
    gen_lang = executing.langs[next(o["type"] for o in dat["files"] if o["name"] == dat["gen_msg"]["generator"])]
    sol_lang = executing.langs[next(o["type"] for o in dat["files"] if o["name"] == dat["gen_msg"]["solution"])]
    file = env.send_file(filepath)
    env.send_file("testlib/testlib.h")
    outfile, ce_msg = gen_lang.compile(file, env)
    if ce_msg:
        return
    sol_file = env.send_file(path + "/file/" + dat["gen_msg"]["solution"])
    sol_exec, ce_msg = sol_lang.compile(sol_file, env)
    if ce_msg:
        return
    i = 1
    tests = []
    seed = dat["gen_msg"]["seed"]
    for k, v in dat["gen_msg"]["counts"].items():
        for j in range(int(v)):
            tests.append((f"{k}_{j + 1}", [str(i), k, seed]))
            i += 1
    exec_cmd = gen_lang.get_execmd(outfile)
    sol_cmd = sol_lang.get_execmd(sol_exec)
    tl = float(dat["timelimit"]) / 1000
    ml = int(dat["memorylimit"])
    os.makedirs(path + "/testcases_gen/", exist_ok=True)
    for test in tests:
        in_file = os.path.abspath(path + "/testcases_gen/" + test[0] + ".in")
        out_file = os.path.abspath(path + "/testcases_gen/" + test[0] + ".out")
        gen_out = env.safe_run(exec_cmd + test[1])
        print(gen_out[1])
        tools.write(gen_out[0], in_file)
        out = env.runwithshell(sol_cmd, env.send_file(in_file), env.filepath(out_file), tl, ml, sol_lang.base_exec_cmd)
        print(out[1])
        result = {o[0]: o[1] for o in (s.split("=") for s in out[0].split("\n")) if len(o) == 2}
        if "1" == result.get("WIFSIGNALED", None) or "0" != result.get("WEXITSTATUS", "0"):
            return
        env.get_file(out_file)
    dat["testcases_gen"] = [{"in": test[0] + ".in", "out": test[0] + ".out", "sample": False} for test in tests]
    tools.write_json(dat, path, "info.json")


@background_actions.bind
def creating_version(pid, description):
    path = "preparing_problems/" + pid
    tools.write(f"建立版本 {description!r}", path, "waiting")
    dat = tools.read_json(path, "info.json")
    if "versions" not in dat:
        dat["versions"] = []
    dat["versions"].append({"description": description, "time": time.time()})
    tools.write_json(dat, path, "info.json")
    shutil.copytree(path, "problems/" + pid, dirs_exist_ok=True)
    tools.remove(path, "waiting")


def runner():
    while True:
        action_data = worker_queue.get()
        try:
            print(f"{action_data=}")
            background_actions.call(action_data["action"], **action_data)
        except Exception as e:
            print(e)
        os.chdir(root_folder)


def add_background_action(obj):
    worker_queue.put(obj)


@actions.default
def action_not_found():
    abort(404)


@actions.bind
def save_general_info(form, pid, path, dat):
    dat["name"] = form["title"]
    dat["memorylimit"] = form["memorylimit"]
    dat["timelimit"] = form["timelimit"]
    tools.write_json(dat, path, "info.json")
    return "general_info"


@actions.bind
def create_version(form, pid, path, dat):
    description = form["description"]
    # system("git add -A", f"preparing_problems/{pid}/")
    # system(f'git commit -m {description!r}', f"preparing_problems/{pid}/")
    # system(f'git pull', f"problems/{pid}/")
    add_background_action({"action": "creating_version", "pid": pid, "description": description})
    return "versions"


@actions.bind
def save_statement(form, pid, path, dat):
    dat["statement"]["main"] = form["statement_main"]
    dat["statement"]["input"] = form["statement_input"]
    dat["statement"]["output"] = form["statement_output"]
    with open(f"preparing_problems/{pid}/info.json", "w") as f:
        json.dump(dat, f, indent=2)
    full = "# Statement\n" + form["statement_main"] + "\n## Input\n" + form[
        "statement_input"] + "\n## Output\n" + form["statement_output"]
    with open(f"preparing_problems/{pid}/statement.md", "w") as f:
        f.write(full)
    with open(f"preparing_problems/{pid}/statement.html", "w") as f:
        parse.dirname = pid
        f.write(run_markdown(full))
    return "statement"


@actions.bind
def upload_zip(form, pid, path, dat):
    input_ext = form["input_ext"]
    output_ext = form["output_ext"]
    file = request.files["zip_file"]
    filename = f"tmp/{str(uuid.uuid4())}.zip"
    file.save(filename)
    zip_file = AESZipFile(filename, "r")
    files: list[AESZipInfo] = zip_file.filelist
    filelist = [o for o in files if not o.is_dir()]
    mp = {}
    for o in filelist:
        if o.filename.endswith(input_ext):
            mp[o.filename[:-len(input_ext)] + output_ext] = o
    ps = []
    for o in filelist:
        if o.filename in mp:
            ps.append((mp[o.filename], o))
    for o in ps:
        print(o[0].filename, o[1].filename)
        with open(path + "/testcases/" + secure_filename(o[0].filename), "wb") as f:
            f.write(zip_file.read(o[0]))
        with open(path + "/testcases/" + secure_filename(o[1].filename), "wb") as f:
            f.write(zip_file.read(o[1]))
        dat["testcases"].append({"in": secure_filename(o[0].filename), "out": secure_filename(o[1].filename),
                                 "sample": "sample" in secure_filename(o[0].filename)})
    tools.write_json(dat, path, "info.json")
    os.remove(filename)
    return "tests"


@actions.bind
def upload_public_file(form, pid, path, dat):
    get_files = request.files.getlist("files")
    for file in get_files:
        if secure_filename(file.filename) == "":
            abort(400)
        file.save(path + "/public_file/" + secure_filename(file.filename))
    return "files"


@actions.bind
def remove_public_file(form, pid, path, dat):
    filename = form["filename"]
    filepath = path + "/public_file/" + secure_filename(filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(400)
    return "files"


@actions.bind
def upload_file(form, pid, path, dat):
    get_files = request.files.getlist("files")
    for file in get_files:
        if secure_filename(file.filename) == "":
            abort(400)
        if os.path.exists(path + "/file/" + secure_filename(file.filename)):
            abort(400)
        file.save(path + "/file/" + secure_filename(file.filename))
        dat["files"].append({"name": secure_filename(file.filename), "type": "C++17"})
    tools.write_json(dat, path, "info.json")
    return "files"


@actions.bind
def create_file(form, pid, path, dat):
    filename = secure_filename(form["filename"])
    tools.create(path, "file", filename)
    dat["files"].append({"name": filename, "type": "C++17"})
    tools.write_json(dat, path, "info.json")
    return "files"


@actions.bind
def remove_file(form, pid, path, dat):
    filename = form["filename"]
    filepath = path + "/file/" + secure_filename(filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(400)
    target = None
    for o in dat["files"]:
        if o["name"] == filename:
            target = o
            break
    if target is None:
        abort(404)
    dat["files"].remove(target)
    tools.write_json(dat, path, "info.json")
    return "files"


@actions.bind
def save_file_content(form, pid, path, dat):
    filename = form["filename"]
    content = form["content"]
    filepath = path + "/file/" + secure_filename(filename)
    target = None
    for o in dat["files"]:
        if o["name"] == filename:
            target = o
            break
    if target is None:
        abort(404)
    target["type"] = form["type"]
    tools.write(content, filepath)
    tools.write_json(dat, path, "info.json")
    return "files"


@actions.bind
def choose_checker(form, pid, path, dat):
    tp = form["checker_type"]
    name = form[tp + "_checker"]
    filepath = ("testlib/checkers/" if tp == "default" else path + "/file/") + name
    if not os.path.isfile(filepath):
        abort(400)
    dat["checker_source"] = [tp, name]
    add_background_action({"action": "compile_checker", "pid": pid})
    tools.write_json(dat, path, "info.json")
    return "judge"


@actions.bind
def save_testcase(form, pid, path, dat):
    modify = json.loads(form["modify"])
    testcases = dat["testcases"]
    if len(modify) != len(testcases):
        abort(400)
    new_testcases = []
    for o in modify:
        obj = testcases[o[0]]
        obj["sample"] = o[1]
        new_testcases.append(obj)
    dat["testcases"] = new_testcases
    tools.write_json(dat, path, "info.json")
    return "tests"


@actions.bind
def save_testcase_gen(form, pid, path, dat):
    modify = json.loads(form["modify"])
    testcases = dat["testcases_gen"]
    if len(modify) != len(testcases):
        abort(400)
    new_testcases = []
    for o in modify:
        obj = testcases[o[0]]
        obj["sample"] = o[1]
        new_testcases.append(obj)
    dat["testcases_gen"] = new_testcases
    tools.write_json(dat, path, "info.json")
    return "tests"


@actions.bind
def set_generator(form, pid, path, dat):
    generator = form["generator"]
    solution = form["solution"]
    seed = form["seed"]
    cnts = {}
    for k in dat["groups"].keys():
        cnts[k] = form["count_" + k]
        if not cnts[k].isdigit():
            abort(400)
    dat["gen_msg"] = {"generator": generator, "solution": solution, "seed": seed, "counts": cnts}
    tools.write_json(dat, path, "info.json")
    add_background_action({"action": "generate_testcase", "pid": pid})
    return "tests"


def action(form: ImmutableMultiDict[str, str]) -> Response:
    pid = secure_filename(form["pid"])
    path = f"preparing_problems/{pid}"
    dat = tools.read_json(path, "info.json")
    tp = actions.call(dat["action"], form, pid, path, dat)
    return redirect(f"/problemsetting/{pid}#{tp}")


def preview(args: MultiDict[str, str]) -> Response:
    pid = args["pid"]
    path = f"preparing_problems/{pid}"
    match args["type"]:
        case "statement":
            with open(path + "/info.json") as f:
                dat = json.load(f)
            with open(path + "/statement.html") as f:
                statement = f.read()
            lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
            samples = [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                       for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if o.get("sample", False)]
            ret = render_template("problem.html", dat=dat, statement=statement,
                                  langs=executing.langs.keys(), lang_exts=lang_exts, pid=pid,
                                  preview=True, samples=enumerate(samples))
            return Response(ret)
        case "public_file":
            return send_file(path + "/public_file/" + secure_filename(args["name"]))
        case "file":
            return send_file(path + "/file/" + secure_filename(args["name"]))
        case "testcases":
            return send_file(path + "/testcases/" + secure_filename(args["name"]))
        case "testcases_gen":
            return send_file(path + "/testcases_gen/" + secure_filename(args["name"]))
    abort(404)


def query_versions(pid):
    path = f"preparing_problems/{pid}/"
    # dat = getout('git log --pretty=format:"%H - %cd - %s"', path)
    out = []
    info = tools.read_json(path, "info.json")
    for o in info.get("versions", []):
        out.append({
            "date": str(int(float(o["time"]) * 1000)),
            "message": o["description"]
        })
    out.reverse()
    for i, o in enumerate(out):
        o["id"] = str(len(out) - i - 1)
    return out
