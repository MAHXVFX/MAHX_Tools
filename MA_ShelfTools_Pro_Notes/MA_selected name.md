# 一级标题

## 二级标题

### 三级标题

#### 四级标题

##### 五级标题

###### 六级标题

**加粗**

*斜体*

~~删除线~~

1. 有序列表
2. 有序列表
    1. a

---

- 无序列表
- 无序列表

- [ ] teskA
- [x] teskB

```python
import hou
scene = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
flipbook_settings = scene.flipbookSettings().stash()
flipbook_settings.frameRange((5,70))
flipbook_settings.resolution((1920,1080))
flipbook_settings.output("$HIP/flip/bbb.$F4.jpg")
scene.flipbook(scene.curViewport(), flipbook_settings)
```