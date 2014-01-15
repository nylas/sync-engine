from wand.image import Image

def generate_thumbnail(img_bytes):
    img = Image(blob=img_bytes)
    # resize to within the box, preserving aspect ratio
    img.transform(resize='250x250')
    return img.make_blob()

def generate_thumbnails(images):
    for filename, img_bytes in images:
        # XXX figure out how to properly auto-orient. for now assume
        # proper orientation.
        # rotation = img.metadata.get('exif:Orientation')
        yield "_".join(['thumb', filename], generate_thumbnail(img_bytes))
