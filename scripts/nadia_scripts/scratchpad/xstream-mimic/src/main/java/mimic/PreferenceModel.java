package mimic;

/**
 * Domain object serialized via XStream — a trimmed stand-in for chainsaw's
 * {@code LogPanelPreferenceModel}. Plain POJO, lives in production code.
 */
public class PreferenceModel {

    private boolean levelIcons;
    private String dateFormatPattern = "EEEEE dd MMMMM yyyy HH:mm:ss.SSS";
    private int loggerPrecision;
    private boolean logTreePanelVisible = true;
    private boolean scrollToBottom = true;
    private boolean toolTips;

    public boolean isLevelIcons() { return levelIcons; }
    public void setLevelIcons(boolean v) { this.levelIcons = v; }

    public String getDateFormatPattern() { return dateFormatPattern; }
    public void setDateFormatPattern(String v) { this.dateFormatPattern = v; }

    public int getLoggerPrecision() { return loggerPrecision; }
    public void setLoggerPrecision(int v) { this.loggerPrecision = v; }

    public boolean isLogTreePanelVisible() { return logTreePanelVisible; }
    public void setLogTreePanelVisible(boolean v) { this.logTreePanelVisible = v; }

    public boolean isScrollToBottom() { return scrollToBottom; }
    public void setScrollToBottom(boolean v) { this.scrollToBottom = v; }

    public boolean isToolTips() { return toolTips; }
    public void setToolTips(boolean v) { this.toolTips = v; }
}
