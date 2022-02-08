import ST7735
from convenience.fonts import *
from PIL import Image, ImageDraw

class Colors:

    RED = (225, 6, 0)
    BLUE = (0, 255, 255)
    WHITE = (255, 255, 255)
    YELLOW = (255, 215, 0)

class Display:

    def __init__(self,
                 port, cs, dc, rst,
                 rotation, offset_top,
                 width=128, height=128,
                 backlight=22,
                 invert=False,
                 spi_speed_hz=24000000):

        self.display = ST7735.ST7735(
            port=port,
            cs=cs,
            # cs=ST7735.BG_SPI_CS_FRONT,  # BG_SPI_CSB_BACK or BG_SPI_CS_FRONT
            dc=dc,  # 27,
            rst=rst,  # 17,
            width=width,
            height=height,
            backlight=backlight,  # 18 for back BG slot, 19 for front BG slot.
            rotation=rotation,  # 180,
            invert=invert,
            spi_speed_hz=spi_speed_hz,
            offset_top=offset_top,
        )

        self.display.begin()

        self.width = width
        self.height = height

        self.display_initialization_message()

    def refresh_display(self, img):

        self.display.display(img)

    def prepare_new_image(self):
        """
        Must be called before drawing, to create a blank canvas.
        """

        img = Image.new("RGB", (self.width, self.height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        return img, draw

    def display_initialization_message(self):

        img, draw = self.prepare_new_image()
        MESSAGE = "INITIALIZING"

        size_x, size_y = draw.textsize(MESSAGE, init_font)
        draw.text((0, 0), MESSAGE, font=init_font, fill=(255, 255, 255))
        self.refresh_display(img)

    def update_thermostat_display(self,
                                  low_temp, high_temp,
                                  local_temp, cur_temp,
                                  status,
                                  last_update,
                                  cur_color, stat_color):

        # Update display with
        #   Target
        #   Current
        #   Status
        #   Last received

        img, draw = self.prepare_new_image()

        # Set messages
        TGT_MESSAGE = f"[{low_temp} - {high_temp}] | {local_temp:.1f}"
        CUR_MESSAGE = f"   {cur_temp:.1f}"
        STATUS_MESSAGE = f"  {status}"
        LAST_MESSAGE = f"Last: {last_update:%H:%M:%S}"

        # Determine message sizes
        small_text_width, small_height = draw.textsize(TGT_MESSAGE, small_font)
        big_text_width, big_height = draw.textsize(TGT_MESSAGE, big_font)

        # Draw baby draw
        draw.text((0, 0), TGT_MESSAGE, font=small_font, fill=(255, 255, 255))
        draw.text(
            (0, small_height * 1.5), CUR_MESSAGE, font=real_big_font, fill=cur_color
        )
        draw.text(
            (0, small_height * 2 + big_height * 1),
            STATUS_MESSAGE,
            font=real_big_font,
            fill=stat_color,
        )
        draw.text(
            (0, small_height * 1 + big_height * 3),
            LAST_MESSAGE,
            font=small_font,
            fill=(255, 255, 255),
        )

        self.refresh_display(img)