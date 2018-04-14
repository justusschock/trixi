import argparse
import os
from collections import defaultdict

import colorlover as cl
import numpy as np
import plotly.graph_objs as go
from flask import Blueprint, Flask, Markup, abort, render_template, request
from plotly.offline import plot
from scipy.signal import savgol_filter

from vislogger.experiment_browser.experimenthelper import ExperimentHelper

IGNORE_KEYS = ("exp_name",
               "experiment_dir",
               "work_dir",
               "config_dir",
               "log_dir",
               "checkpoint_dir",
               "img_dir",
               "plot_dir",
               "save_dir",
               "result_dir",
               "init_time",
               "description")

COLORMAP = cl.scales["8"]["qual"]["Dark2"]

# Read in base directory
parser = argparse.ArgumentParser()
parser.add_argument("base_directory",
                    help="Give the path to the base directory of your project files",
                    type=str)
parser.add_argument("-d", "--debug", action="store_true",
                    help="Turn debug mode on, eg. for live reloading.")
args = parser.parse_args()
base_dir = args.base_directory

# The actual flask app lives in the package directory. The blueprint allows us
# to specify an additional static folder and we use that to allow access to the
# experiment files
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
blueprint = Blueprint("data", __name__, static_url_path=base_dir, static_folder=base_dir)
app.register_blueprint(blueprint)


def process_base_dir(base_dir):
    config_keys = set()
    result_keys = set()
    exps = []
    default_val = "-"
    short_len = 25

    ### Load Experiments with keys / different param values
    for sub_dir in sorted(os.listdir(base_dir)):
        dir_path = os.path.join(base_dir, sub_dir)
        if os.path.isdir(dir_path):
            exp = ExperimentHelper(dir_path)
            config_keys.update(list(exp.config.keys()))
            result_keys.update(list(exp.get_results().keys()))
            exps.append(exp)

    ### Remove unwanted keys
    config_keys -= set(IGNORE_KEYS)

    ### Generate table rows
    sorted_c_keys = sorted(config_keys, key=lambda x: str(x).lower())
    sorted_r_keys = sorted(result_keys, key=lambda x: str(x).lower())

    rows = []
    for exp in exps:
        config_row = []
        for key in sorted_c_keys:
            attr_strng = str(exp.config.get(key, default_val))
            config_row.append((attr_strng, attr_strng[:short_len]))
        result_row = []
        for key in sorted_r_keys:
            attr_strng = str(exp.get_results().get(key, default_val))
            result_row.append((attr_strng, attr_strng[:short_len]))
        rows.append((os.path.basename(exp.work_dir),
                     str(exp.config.get("exp_name", default_val)),
                     str(exp.config.get("init_time", default_val)),
                     str(exp.config.get("description", default_val)),
                     config_row, result_row))

    return {"ccols": sorted_c_keys, "rcols": sorted_r_keys, "rows": rows}


# def get_experiment_content(experiment_dir):
#
#     exp = ExperimentHelper(experiment_dir)
#     results = exp.get_results()
#     graphs = make_graphs(results)
#     images = exp.get_images()
#
#     return {"graphs": graphs, "images": images}


def group_images(images):
    images.sort()
    group_dict = defaultdict(list)

    for img in images:
        base_name = os.path.splitext(os.path.basename(img))[0]
        base_name = ''.join(e for e in base_name if e.isalpha())

        group_dict[base_name].append(img)

    return group_dict


def make_graphs(results, trace_options=None, layout_options=None):
    if trace_options is None:
        trace_options = {}
    if layout_options is None:
        layout_options = {}

    graphs = []

    for group in results:

        layout = go.Layout(title=group, **layout_options)
        traces = []

        for r, result in enumerate(results[group]):

            y = np.array(results[group][result]["data"])
            x = np.array(results[group][result]["epoch"])

            do_filter = len(y) >= 1000
            opacity = 0.2 if do_filter else 1.

            traces.append(go.Scatter(x=x, y=y, opacity=opacity, name=result,
                                     line=dict(color=COLORMAP[r % len(COLORMAP)]), **trace_options))
            if do_filter:
                def filter_(x):
                    return savgol_filter(x, max(5, 2 * (len(y) // 50) + 1), 3)

                traces.append(go.Scatter(x=x, y=filter_(y), name=result + " smoothed",
                                         line=dict(color=COLORMAP[r % len(COLORMAP)]), **trace_options))

        graphs.append(Markup(plot({"data": traces, "layout": layout},
                                  output_type="div",
                                  include_plotlyjs=False,
                                  show_link=False)))

    return graphs


def merge_results(experiment_names, result_list):
    merged_results = {}

    for r, result in enumerate(result_list):
        for label in result.keys():
            if label not in merged_results:
                merged_results[label] = {}
            for key in result[label].keys():
                new_key = "_".join([experiment_names[r], key])
                merged_results[label][new_key] = result[label][key]

    return merged_results


@app.route("/")
def overview():
    try:
        base_info = process_base_dir(base_dir)
        base_info["title"] = base_dir
        return render_template("overview.html", **base_info)
    except Exception as e:
        print(e.__repr__())
        abort(500)


@app.route('/experiment', methods=['GET'])
def experiment():
    experiment_paths = request.args.getlist('exp')

    experiments = []

    # Get all Experiments
    for experiment_path in experiment_paths:
        exp = ExperimentHelper(os.path.join(base_dir, experiment_path), name=experiment_path)
        experiments.append(exp)

    # Assign unique names
    exp_names = [exp.exp_name for exp in experiments]
    if len(exp_names) > len(set(exp_names)):
        for i, exp in enumerate(experiments):
            exp.exp_name += str(i)
    exp_names = [exp.exp_name for exp in experiments]

    # Site Content
    content = {}

    # Get config

    default_val = "-"
    combi_config = {}
    exp_names = [exp.exp_name for exp in experiments]
    exp_configs = [exp.config for exp in experiments]
    config_keys = set([k for c in exp_configs for k in c.keys()])
    for k in sorted(config_keys):
        combi_config[k] = []
        for conf in exp_configs:
            combi_config[k].append(conf.get(k, default_val))


    # Get images
    images = {}
    image_keys = []
    image_path = exp.img_dir
    for exp in experiments:
        exp_images = exp.get_images()
        img_groups = group_images(exp_images)
        images[exp.exp_name] = img_groups
        image_keys += (list(img_groups.keys()))
    image_keys.sort()

    # Get plot results
    results = []
    for exp in experiments:
        results.append(exp.get_results_log())
    results = merge_results(exp_names, results)

    content["graphs"] = make_graphs(results)
    content["title"] = experiments
    content["images"] = {"img_path": image_path, "imgs": images, "img_keys": image_keys}
    content["config"] = {"exps" : exp_names, "configs": combi_config, "ckeys": config_keys}

    return render_template('experiment.html', **content)


if __name__ == "__main__":
    app.run(debug=args.debug)
