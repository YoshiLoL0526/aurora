# Cobertura por componente

Cada componente público tiene una prueba de render, una de interacción con `Pilot`,
una del árbol de accesibilidad (rol y nombre) y, si es interactivo, una de teclado.
La tabla se genera desde `tests/test_coverage.py`, que comprueba que cada prueba
existe y trata de ese componente; las comunes a todos están en ese mismo archivo:

- `coverage::component_renders_with_its_defaults` pinta cada uno con sus valores por
  defecto en el tema claro y en el oscuro;
- `coverage::component_announces_its_role_and_name` busca su rol y su nombre en el árbol
  de accesibilidad;
- `coverage::static_components_take_neither_focus_nor_clicks` comprueba que los
  decorativos no entran en el orden de Tab ni se quedan con los clics.

| Componente | Render | Interacción | Accesibilidad | Teclado |
| --- | --- | --- | --- | --- |
| `accordion` | `test_coverage::component_renders_with_its_defaults` | `test_components::accordion_toggles_sections` | `test_coverage::component_announces_its_role_and_name` | `test_coverage::accordion_header_toggles_with_enter` |
| `avatar` | `test_components::avatar_initials_and_stable_color` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `badge` | `test_coverage::component_renders_with_its_defaults` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `button` | `test_coverage::component_renders_with_its_defaults` | `test_pilot::click_runs_handler_and_rebuilds` | `test_coverage::component_announces_its_role_and_name` | `test_keyboard::enter_activates_focused_node` |
| `canvas` | `test_canvas::figures_are_painted_at_their_coordinates` | `test_canvas::canvas_receives_clicks` | `test_coverage::component_announces_its_role_and_name` | La app lo da con `on_key`: el lienzo no tiene semántica propia |
| `card` | `test_coverage::component_renders_with_its_defaults` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `chart` | `test_charts::repaints_from_the_raster_cache_look_the_same` | `test_charts::zoom_with_a_descending_x` | `test_a11y::el_grafico_con_zoom_anuncia_su_ventana_y_sus_teclas` | `test_charts::keyboard_zooms_pans_and_resets_the_focused_chart` |
| `checkbox` | `test_components::checkbox_draws_mark_when_checked` | `test_components::checkbox_toggles_signal_with_click_and_keyboard` | `test_a11y::la_casilla_anuncia_su_estado_y_se_actualiza` | `test_components::checkbox_toggles_signal_with_click_and_keyboard` |
| `color_picker` | `test_coverage::component_renders_with_its_defaults` | `test_pickers::color_picker_palette_and_hex_field` | `test_pickers::color_picker_announces_its_parts` | `test_pickers::color_picker_square_and_hue_by_drag_and_keyboard` |
| `combobox` | `test_coverage::component_renders_with_its_defaults` | `test_pickers::combobox_filters_ignoring_case_and_accents` | `test_coverage::component_announces_its_role_and_name` | `test_pickers::combobox_keyboard_highlight_and_enter` |
| `date_picker` | `test_pickers::pickers_render_selected_day_in_primary` | `test_pickers::date_picker_opens_on_the_value_month_and_chooses` | `test_pickers::date_picker_cells_announce_full_dates` | `test_pickers::date_picker_keyboard_moves_days_weeks_and_months` |
| `dialog` | `test_coverage::component_renders_with_its_defaults` | `test_components::dialog_centers_the_card_and_takes_focus` | `test_coverage::component_announces_its_role_and_name` | `test_components::dialog_closes_with_escape` |
| `divider` | `test_components::divider_horizontal_and_vertical` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `field` | `test_coverage::component_renders_with_its_defaults` | `test_components::field_shows_label_and_error` | `test_coverage::component_announces_its_role_and_name` | `test_input::tab_leaves_the_field_and_space_types` |
| `markdown` | `test_coverage::component_renders_with_its_defaults` | `test_richtext::markdown_links_call_on_link_with_the_url` | `test_coverage::component_announces_its_role_and_name` | `test_richtext::markdown_links_are_reached_with_tab_and_followed_with_enter` |
| `menu` | `test_coverage::component_renders_with_its_defaults` | `test_components::menu_opens_chooses_and_closes` | `test_coverage::component_announces_its_role_and_name` | `test_components::menu_closes_on_outside_click_and_escape` |
| `number_input` | `test_coverage::component_renders_with_its_defaults` | `test_pickers::number_input_typing_assigns_valid_numbers` | `test_pickers::number_input_is_a_spinbutton_for_screen_readers` | `test_pickers::number_input_arrows_and_buttons_step_and_clamp` |
| `pages` | `test_coverage::component_renders_with_its_defaults` | `test_components::pages_switches_views` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `popover` | `test_render::popover_paints_its_panel_where_it_was_placed` | `test_pilot::popover_flips_above_when_there_is_no_room_below` | `test_coverage::component_announces_its_role_and_name` | `test_pilot::popover_opens_below_and_closes_with_escape_or_outside_click` |
| `progress` | `test_coverage::component_renders_with_its_defaults` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `radio` | `test_coverage::component_renders_with_its_defaults` | `test_components::radio_selects_one_option` | `test_a11y::el_grupo_de_radios_anuncia_posicion_y_seleccion` | `test_coverage::radio_groups_move_with_arrows` |
| `rich_text` | `test_coverage::component_renders_with_its_defaults` | `test_richtext::link_spans_receive_clicks_and_are_announced_as_links` | `test_coverage::component_announces_its_role_and_name` | `test_richtext::links_join_the_tab_order_and_activate_with_enter` |
| `segmented` | `test_components::segmented_thumb_slides` | `test_components::segmented_thumb_slides` | `test_coverage::component_announces_its_role_and_name` | `test_coverage::radio_groups_move_with_arrows` |
| `select` | `test_coverage::component_renders_with_its_defaults` | `test_components::select_opens_chooses_and_closes` | `test_coverage::component_announces_its_role_and_name` | `test_components::select_arrow_keys_change_value` |
| `skeleton` | `test_components::skeleton_draws_lines_with_a_shorter_last` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `slider` | `test_coverage::component_renders_with_its_defaults` | `test_components::slider_drags_and_clamps` | `test_a11y::el_slider_anuncia_valor_y_rango` | `test_coverage::slider_moves_with_arrows_and_clamps` |
| `sortable` | `test_render::sortable_marks_where_the_item_will_land` | `test_pilot::sortable_reorders_with_the_pointer` | `test_a11y::sortable_is_a_list_and_announces_keyboard_moves` | `test_pilot::sortable_keyboard_grab_move_drop_and_cancel` |
| `spinner` | `test_components::spinner_pulses_and_never_rests` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `splitter` | `test_render::splitter_paints_a_divider_line_between_the_panes` | `test_pilot::splitter_drag_resizes_and_respects_both_minimums` | `test_coverage::component_announces_its_role_and_name` | `test_pilot::splitter_keyboard_and_screen_reader_actions` |
| `stat` | `test_coverage::component_renders_with_its_defaults` | `test_coverage::static_components_take_neither_focus_nor_clicks` | `test_coverage::component_announces_its_role_and_name` | No es interactivo |
| `switch` | `test_components::switch_moves_knob` | `test_components::switch_moves_knob` | `test_a11y::el_interruptor_es_un_switch` | `test_coverage::switch_toggles_with_space_and_enter` |
| `table` | `test_table::renders_header_rows_and_stripes` | `test_table::clicking_a_header_cycles_ascending_descending_original` | `test_coverage::component_announces_its_role_and_name` | `test_coverage::table_headers_sort_from_the_keyboard` |
| `tabs` | `test_components::tabs_underline_fades_between_tabs` | `test_components::tabs_click_and_arrow_keys` | `test_coverage::component_announces_its_role_and_name` | `test_components::tabs_click_and_arrow_keys` |
| `text_input` | `test_coverage::component_renders_with_its_defaults` | `test_input::enter_submits_single_line` | `test_coverage::component_announces_its_role_and_name` | `test_input::arrows_and_shift_select_then_typing_replaces` |
| `textarea` | `test_coverage::component_renders_with_its_defaults` | `test_input::textarea_newlines_vertical_moves_and_growth` | `test_coverage::component_announces_its_role_and_name` | `test_input::textarea_newlines_vertical_moves_and_growth` |
| `time_picker` | `test_coverage::component_renders_with_its_defaults` | `test_pickers::time_picker_lists_steps_and_chooses` | `test_pickers::time_picker_opens_with_the_value_in_view_and_announces_options` | `test_pickers::time_picker_keyboard_limits_and_12_hour_format` |
| `title_bar` | `test_render::title_bar_paints_the_window_buttons` | `test_pilot::title_bar_buttons_act_on_their_window` | `test_a11y::title_bar_buttons_are_named_buttons` | `test_coverage::title_bar_buttons_stay_out_of_the_tab_order_but_answer_readers` |
| `toast` | `test_coverage::component_renders_with_its_defaults` | `test_components::toast_shows_dismisses_and_animates` | `test_coverage::component_announces_its_role_and_name` | `test_coverage::toast_close_button_works_from_the_keyboard` |
| `tooltip` | `test_coverage::component_renders_with_its_defaults` | `test_components::tooltip_appears_after_delay_and_hides_on_click` | `test_coverage::component_announces_its_role_and_name` | Lo lleva el control que envuelve; el aviso es solo de puntero |
| `tree` | `test_render::tree_highlights_the_selected_row_and_indents_children` | `test_pilot::tree_click_selects_and_chevron_expands` | `test_pilot::tree_announces_levels_positions_and_expansion` | `test_pilot::tree_keyboard_follows_the_treeview_pattern` |
| `virtual_list` | `test_coverage::component_renders_with_its_defaults` | `test_virtual_list::scrolling_moves_the_visible_range` | `test_coverage::component_announces_its_role_and_name` | `test_coverage::virtual_list_scrolls_with_page_keys` |
