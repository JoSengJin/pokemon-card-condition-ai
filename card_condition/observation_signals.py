"""Fixed pixel descriptions; no label inference or train/validation fitting."""
from PIL import ImageChops, ImageStat


def pixel_signals(image):
    gray=image.convert('L')
    width,height=gray.size
    stat=ImageStat.Stat(gray)
    differences=[]
    if width>1:
        differences.append(ImageStat.Stat(ImageChops.difference(
            gray.crop((1,0,width,height)),gray.crop((0,0,width-1,height)))).mean[0])
    if height>1:
        differences.append(ImageStat.Stat(ImageChops.difference(
            gray.crop((0,1,width,height)),gray.crop((0,0,width,height-1)))).mean[0])
    histogram=gray.histogram()
    return dict(luminance_mean=stat.mean[0],luminance_std=stat.stddev[0],
        gradient_energy=sum(differences)/len(differences) if differences else 0.,
        bright_fraction=sum(histogram[245:])/(width*height),
        dark_fraction=sum(histogram[:26])/(width*height))


def spatial_signals(image):
    width,height=image.size
    size=min(3,width,height)
    cells=[]
    for y in range(size):
        for x in range(size):
            box=(x*width//size,y*height//size,(x+1)*width//size,(y+1)*height//size)
            cells.append(dict(column=x,row=y,signals=pixel_signals(image.crop(box))))
    signals=pixel_signals(image)
    means=[c['signals']['luminance_mean'] for c in cells]
    signals['cell_luminance_spread']=max(means)-min(means)
    return dict(size=[width,height],grid_size=size,signals=signals,cells=cells)


def local_color_texture(image):
    if image.size != (224,224):
        raise ValueError('Local descriptor requires the unchanged 224px input')
    values=[]
    for y in range(3):
        for x in range(3):
            cell=image.crop((x*224//3,y*224//3,(x+1)*224//3,(y+1)*224//3))
            signals=pixel_signals(cell)
            saturation=ImageStat.Stat(cell.convert('HSV').getchannel('S')).mean[0]
            red,green,blue=cell.convert('RGB').split()
            neutral=ImageStat.Stat(ImageChops.darker(ImageChops.darker(red,green),blue)).mean[0]
            values.extend([signals['luminance_mean']/255,signals['gradient_energy']/255,
                           saturation/255,neutral/255])
    return values
