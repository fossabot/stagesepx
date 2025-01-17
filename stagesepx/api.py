"""
high level API
"""
import os
import typing

from stagesepx.cutter import VideoCutter
from stagesepx.cutter import VideoCutResult
from stagesepx.classifier import SVMClassifier, ClassifierResult
from stagesepx.reporter import Reporter
from stagesepx import constants
from stagesepx.video import VideoObject


def one_step(
    video: typing.Union[str, VideoObject],
    output_path: str = None,
    threshold: float = 0.95,
    frame_count: int = 5,
    compress_rate: float = 0.2,
    target_size: typing.Tuple[int, int] = None,
    offset: int = 3,
    limit: int = None,
):
    """
    one step => cut, classifier, draw

    :param video: video path or object
    :param output_path: output path (dir)
    :param threshold: float, 0-1, default to 0.95. decided whether a range is stable. larger => more unstable ranges
    :param frame_count: default to 5, and finally you will get 5 frames for each range
    :param compress_rate: before_pic * compress_rate = after_pic. default to 0.2
    :param target_size: (100, 200)
    :param offset:
        it will change the way to decided whether two ranges can be merged
        before: first_range.end == second_range.start
        after: first_range.end + offset >= secord_range.start
    :param limit: ignore some ranges which are too short, 5 means ignore stable ranges which length < 5
    :return:
    """

    if isinstance(video, str):
        video = VideoObject(video)

    # --- cutter ---
    res, data_home = cut(
        video,
        output_path,
        threshold=threshold,
        frame_count=frame_count,
        compress_rate=compress_rate,
        target_size=target_size,
        offset=offset,
        limit=limit,
    )

    # --- classify ---
    classify_result = classify(
        video,
        data_home=data_home,
        compress_rate=compress_rate,
        target_size=target_size,
        offset=offset,
        limit=limit,
    )

    # --- draw ---
    r = Reporter()
    r.draw(
        classify_result,
        report_path=os.path.join(data_home, constants.REPORT_FILE_NAME),
        cut_result=res,
        # kwargs of get_range
        # otherwise these thumbnails may become different
        threshold=threshold,
        limit=limit,
        offset=offset,
    )


def cut(
    video: typing.Union[str, VideoObject],
    output_path: str = None,
    threshold: float = 0.95,
    frame_count: int = 5,
    compress_rate: float = 0.2,
    target_size: typing.Tuple[int, int] = None,
    offset: int = 3,
    limit: int = None,
) -> typing.Tuple[VideoCutResult, str]:
    """
    cut the video, and get series of pictures (with tag)

    :param video: video path or object
    :param output_path: output path (dir)
    :param threshold: float, 0-1, default to 0.95. decided whether a range is stable. larger => more unstable ranges
    :param frame_count: default to 5, and finally you will get 5 frames for each range
    :param compress_rate: before_pic * compress_rate = after_pic. default to 0.2
    :param target_size: (100, 200)
    :param offset:
        it will change the way to decided whether two ranges can be merged
        before: first_range.end == second_range.start
        after: first_range.end + offset >= secord_range.start
    :param limit: ignore some ranges which are too short, 5 means ignore stable ranges which length < 5

    :return: tuple, (VideoCutResult, data_home)
    """
    if isinstance(video, str):
        video = VideoObject(video)

    cutter = VideoCutter()
    res = cutter.cut(video, compress_rate=compress_rate, target_size=target_size)
    stable, unstable = res.get_range(threshold=threshold, limit=limit, offset=offset)

    data_home = res.pick_and_save(stable, frame_count, to_dir=output_path)
    res_json_path = os.path.join(
        output_path or data_home, constants.CUT_RESULT_FILE_NAME
    )
    res.dump(res_json_path)
    return res, data_home


def train(
    data_home: str,
    save_to: str,
    compress_rate: float = 0.2,
    target_size: typing.Tuple[int, int] = None,
):
    """
    build a trained model with a dataset

    :param data_home: output path (dir)
    :param save_to: model will be saved to this path
    :param compress_rate: before_pic * compress_rate = after_pic. default to 0.2
    :param target_size: (100, 200)
    """
    assert os.path.isdir(data_home), f"dir {data_home} not existed"
    assert not os.path.isfile(save_to), f"file {save_to} already existed"
    cl = SVMClassifier(compress_rate=compress_rate, target_size=target_size)
    cl.load(data_home)
    cl.train()
    cl.save_model(save_to)


def classify(
    video: typing.Union[str, VideoObject],
    data_home: str = None,
    model: str = None,
    # optional: these args below are sent for `cutter`
    compress_rate: float = 0.2,
    target_size: typing.Tuple[int, int] = None,
    offset: int = 3,
    limit: int = None,
    threshold: float = 0.95,
) -> typing.List[ClassifierResult]:
    """
    classify a video with some tagged pictures
    optional: if you have changed the default value in `cut`, you'd better keep them(offset and limit) equal.

    :param video: video path or object
    :param data_home: output path (dir)
    :param model: LinearSVC model (path)
    :param compress_rate: before_pic * compress_rate = after_pic. default to 0.2
    :param target_size: (100, 200)
    :param offset:
        it will change the way to decided whether two ranges can be merged
        before: first_range.end == second_range.start
        after: first_range.end + offset >= secord_range.start
    :param limit: ignore some ranges which are too short, 5 means ignore stable ranges which length < 5
    :param threshold: cutter threshold

    :return: typing.List[ClassifierResult]
    """
    if isinstance(video, str):
        video = VideoObject(video)

    assert data_home or model, "classification should based on dataset or trained model"
    cl = SVMClassifier(compress_rate=compress_rate, target_size=target_size)

    if model:
        cl.load_model(model)
    else:
        cl.load(data_home)
        cl.train()
    # re cut
    cut_result, _ = cut(video, compress_rate=compress_rate, threshold=threshold)
    stable, _ = cut_result.get_range(offset=offset, limit=limit)
    return cl.classify(video, stable)


__all__ = ("cut", "classify", "one_step", "train")
