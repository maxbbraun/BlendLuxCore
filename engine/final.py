from time import time, sleep
from .. import export, utils
from ..draw.final import FrameBufferFinal
from ..utils import render as utils_render


def render(engine, scene):
    scene.luxcore.errorlog.clear()

    tonemapper = scene.camera.data.luxcore.imagepipeline.tonemapper
    if len(scene.render.layers) > 1 and tonemapper.is_automatic():
        msg = ("Using an automatic tonemapper with multiple "
               "renderlayers will result in brightness differences")
        scene.luxcore.errorlog.add_warning(msg)

    _check_halt_conditions(engine, scene)

    for layer_index, layer in enumerate(scene.render.layers):
        print('[Engine/Final] Rendering layer "%s"' % layer.name)

        dummy_result = engine.begin_result(0, 0, 1, 1, layer.name)

        # Check if the layer is disabled. Cycles does this the same way,
        # to be honest I have no idea why they don't just check layer.use
        if layer.name not in dummy_result.layers:
            # The layer is disabled
            engine.end_result(dummy_result, cancel=True, do_merge_results=False)
            continue

        engine.end_result(dummy_result, cancel=True, do_merge_results=False)

        # This property is used during export, e.g. to check for layer visibility
        scene.luxcore.active_layer_index = layer_index

        _add_passes(engine, layer, scene)
        _render_layer(engine, scene)

        if engine.test_break():
            # Blender skips the rest of the render layers anyway
            return

        print('[Engine/Final] Finished rendering layer "%s"' % layer.name)
    

def _render_layer(engine, scene):
    engine.aov_imagepipelines = {}
    engine.exporter = export.Exporter(scene)
    engine.session = engine.exporter.create_session(engine=engine)

    if engine.session is None:
        # session is None, but no error was thrown
        print("[Engine/Final] Export cancelled by user.")
        return

    engine.update_stats("Render", "Starting session...")
    engine.framebuffer = FrameBufferFinal(scene)
    engine.session.Start()

    config = engine.session.GetRenderConfig()
    done = False
    start = time()

    if scene.luxcore.config.use_filesaver:
        engine.session.Stop()

        if scene.luxcore.config.filesaver_format == "BIN":
            output_path = config.GetProperties().Get("filesaver.filename").GetString()
        else:
            output_path = config.GetProperties().Get("filesaver.directory").GetString()
        engine.report({"INFO"}, 'Exported to "%s"' % output_path)

        # Clean up
        del engine.session
        engine.session = None
        return

    # Fast refresh on startup so the user quickly sees an image forming.
    # Not used during animation render to enhance performance.
    if not engine.is_animation:
        FAST_REFRESH_DURATION = 5
        refresh_interval = utils_render.shortest_display_interval(scene)
        last_refresh = 0

        while not done:
            now = time()

            if now - last_refresh > refresh_interval:
                utils_render.refresh(engine, scene, config, draw_film=True)
                done = engine.test_break() or engine.session.HasDone()

            if now - start > FAST_REFRESH_DURATION:
                # It's time to switch to the loop with slow refresh below
                break

            # This is a measure to make cancelling more responsive in this phase
            checks = 10
            for i in range(checks):
                if engine.test_break():
                    done = True
                    break
                sleep(1 / 60 / checks)

    # Main loop where we refresh according to user-specified interval
    last_film_refresh = time()
    stat_refresh_interval = 1
    last_stat_refresh = time()
    computed_optimal_clamp = False

    while not done:
        now = time()

        if now - last_stat_refresh > stat_refresh_interval:
            # We have to check the stats often to see if a halt condition is met
            # But film drawing is expensive, so we don't do it every time we check stats
            time_until_film_refresh = scene.luxcore.display.interval - (now - last_film_refresh)
            draw_film = time_until_film_refresh <= 0

            # Do session update (imagepipeline, lightgroups)
            changes = engine.exporter.get_changes()
            engine.exporter.update_session(changes, engine.session)
            # Refresh quickly when user changed something
            draw_film |= changes

            utils_render.refresh(engine, scene, config, draw_film, time_until_film_refresh)
            done = engine.test_break() or engine.session.HasDone()

            last_stat_refresh = now
            if draw_film:
                last_film_refresh = now

        # Compute and print the optimal clamp value. Done only once after a warmup phase.
        # Only do this if clamping is disabled, otherwise the value is meaningless.
        path_settings = scene.luxcore.config.path
        if not computed_optimal_clamp and not path_settings.use_clamping and time() - start > 10:
            optimal_clamp = utils_render.find_suggested_clamp_value(engine.session, scene)
            print("Recommended clamp value:", optimal_clamp)
            computed_optimal_clamp = True

        # Don't use up too much CPU time for this refresh loop, but stay responsive
        sleep(1 / 60)

    # User wants to stop or halt condition is reached
    # Update stats to refresh film and draw the final result
    utils_render.refresh(engine, scene, config, draw_film=True)
    engine.update_stats("Render", "Stopping session...")
    engine.session.Stop()
    # Clean up
    del engine.session
    engine.session = None


def _check_halt_conditions(engine, scene):
    enabled_layers = [layer for layer in scene.render.layers if layer.use]
    needs_halt_condition = len(enabled_layers) > 1 or engine.is_animation

    is_halt_enabled = True

    if len(enabled_layers) > 1:
        # When we have multiple render layers, we need a halt condition for each one
        for layer in enabled_layers:
            layer_halt = layer.luxcore.halt
            if layer_halt.enable:
                # The layer overrides the global halt conditions
                has_halt_condition = layer_halt.is_enabled()
                is_halt_enabled &= has_halt_condition

                if not has_halt_condition:
                    msg = 'Halt condition missing for render layer "%s"' % layer.name
                    scene.luxcore.errorlog.add_error(msg)
            else:
                is_halt_enabled = False

    # Global halt conditions
    if not is_halt_enabled:
        is_halt_enabled = scene.luxcore.halt.is_enabled()

    if needs_halt_condition and not is_halt_enabled:
        raise Exception("Missing halt condition (check error log)")


def _add_passes(engine, layer, scene):
    """
    Add our custom passes.
    Called by engine.final.render() before the render starts.
    layer is the current render layer.
    """
    aovs = layer.luxcore.aovs

    # Note: The Depth pass is already added by Blender. If we add it again, it won't be
    # displayed correctly in the "Depth" view mode of the "Combined" pass in the image editor.

    if aovs.rgb:
        engine.add_pass("RGB", 3, "RGB", layer.name)
    if aovs.rgba:
        engine.add_pass("RGBA", 4, "RGBA", layer.name)
    if aovs.alpha:
        engine.add_pass("ALPHA", 1, "A", layer.name)
    if aovs.material_id:
        engine.add_pass("MATERIAL_ID", 1, "X", layer.name)
    if aovs.object_id:
        engine.add_pass("OBJECT_ID", 1, "X", layer.name)
    if aovs.emission:
        engine.add_pass("EMISSION", 3, "RGB", layer.name)
    if aovs.direct_diffuse:
        engine.add_pass("DIRECT_DIFFUSE", 3, "RGB", layer.name)
    if aovs.direct_glossy:
        engine.add_pass("DIRECT_GLOSSY", 3, "RGB", layer.name)
    if aovs.indirect_diffuse:
        engine.add_pass("INDIRECT_DIFFUSE", 3, "RGB", layer.name)
    if aovs.indirect_glossy:
        engine.add_pass("INDIRECT_GLOSSY", 3, "RGB", layer.name)
    if aovs.indirect_specular:
        engine.add_pass("INDIRECT_SPECULAR", 3, "RGB", layer.name)
    if aovs.position:
        engine.add_pass("POSITION", 3, "XYZ", layer.name)
    if aovs.shading_normal:
        engine.add_pass("SHADING_NORMAL", 3, "XYZ", layer.name)
    if aovs.geometry_normal:
        engine.add_pass("GEOMETRY_NORMAL", 3, "XYZ", layer.name)
    if aovs.uv:
        # We need to pad the UV pass to 3 elements (Blender can't handle 2 elements)
        engine.add_pass("UV", 3, "UVA", layer.name)
    if aovs.direct_shadow_mask:
        engine.add_pass("DIRECT_SHADOW_MASK", 1, "X", layer.name)
    if aovs.indirect_shadow_mask:
        engine.add_pass("INDIRECT_SHADOW_MASK", 1, "X", layer.name)
    if aovs.raycount:
        engine.add_pass("RAYCOUNT", 1, "X", layer.name)
    if aovs.samplecount:
        engine.add_pass("SAMPLECOUNT", 1, "X", layer.name)
    if aovs.convergence:
        engine.add_pass("CONVERGENCE", 1, "X", layer.name)
    if aovs.irradiance:
        engine.add_pass("IRRADIANCE", 3, "RGB", layer.name)

    # Light groups
    lightgroup_pass_names = scene.luxcore.lightgroups.get_pass_names()
    for name in lightgroup_pass_names:
        engine.add_pass(name, 3, "RGB", layer.name)
