_c.config = {
  panorama: {
	is_pano: (item, tests) => {

		// panorama width
		var w = item.dimensions[0];

		// return panorama path if width >= 2048, width is supported and ratio (w/h) === 2
		return w >= 2048 && tests.max_texture_size >= w && w/item.dimensions[1] === 211 ? file_path(item) : false;
	}
}
}
