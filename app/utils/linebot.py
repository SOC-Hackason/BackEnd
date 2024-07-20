import requests
from app.utils.gmail import get_unread_message, get_title_from_ids

async def list_message(service, max_results=12):
    unread_messages = get_unread_message(service)
    msg_ids = [msg["id"] for msg in unread_messages["messages"]]
    msg_ids = msg_ids[:max_results]
    titles = await get_title_from_ids(service, msg_ids)
    data =  {"message": titles, "msg_ids": msg_ids}
    titles = data["message"]
    msg_ids = data["msg_ids"]

    flex_contents = []
    for title, msg_id in zip(titles, msg_ids):
        flex_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "wrap": True,
                    "weight": "bold",
                    "size": "xs",
                    "maxLines": 2,
                    "flex": 3,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "詳細",
                        "data": f"msg_id={msg_id}",
                        "displayText": "詳細を表示します"
                    },
                    "style": "primary",
                    "color": "#00B900",
                    "height": "sm",
                    "margin": "sm",
                    "flex": 1,
                }
            ],
            "alignItems": "center",
            "paddingAll": "sm",
            "margin": "xs",
        })

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "メール一覧(通知)",
                    "weight": "bold",
                    "size": "xl",
                    "align": "center"
                },
                {
                    "type": "separator",
                    "margin": "sm",
                    "color": "#000000"
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": flex_contents
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "すべて既読にする",
                        "data": f"spaction=read_all%{','.join(msg_ids)}",
                        "displayText": "すべてのメールを既読にします"
                    },
                    "style": "primary",
                    "color": "#00B900",
                    "height": "sm"
                }
            ],
            "margin": "sm"
        }
    }

    messages = [
        {
            "type": "flex",
            "altText": "メール一覧",
            "contents": bubble
        }
    ]

    return messages

def get_(x:dict, y:str, z:str):
    item = x.get(y)
    if item is None:
        return z
    return item

def flex_one_mail(data, msg_id):
    _from = get_(data, "from", "Unknown")
    _from = _from.split("<")[0]
    _to = get_(data, "to", "Unknown")
    _subject = get_(data, "subject", "No Subject")
    _message = get_(data, "message", "No Message")
    _importance = data["importance"]
    _category = data["category"]
    _importance_index = 3 - LABELS_IMPORTANCE.index(_importance)
    _is_English = data.get("is_English", False)
    print(data)
    print(_to)
    bubble = {
        "type": "bubble",
        "styles": {
            "body": {
                "separator": True,
                "separatorColor": "#DDDDDD"
            }
        },
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": _subject,
                    "maxLines": 3,
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True,
                    "flex": 3
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "alignItems": "center",
                    "contents": [
                        {
                            "type": "image",
                            "url": "https://developers-resource.landpress.line.me/fx/img/review_gold_star_28.png",
                            "size": "30px"
                        }
                        for _ in range(_importance_index)
                    ],
                }
            ],
            "backgroundColor": "#EEEEEE",
            "paddingAll": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "From:",
                            "size": "sm",
                            "color": "#888888",
                            "flex": 1
                        },
                        {
                            "type": "text",
                            "text": _from,
                            "size": "sm",
                            "wrap": True,
                            "flex": 4
                        }
                    ],
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "To:",
                            "size": "sm",
                            "color": "#888888",
                            "flex": 1
                        },
                        {
                            "type": "text",
                            "text": _to,
                            "size": "sm",
                            "wrap": True,
                            "flex": 4
                        }
                    ],
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": _message,
                            "wrap": True,
                            "size": "sm",
                            "maxLines": 10,
                        }
                    ],
                    "backgroundColor": "#F7F7F7",
                    "paddingAll": "md",
                    "cornerRadius": "md",
                    "margin": "md",
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                { 
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "Reply" if _is_English else "返信",
                            "data": f"action=reply%{msg_id}",
                            "displayText": "返信を作成します"
                        },
                        "color": "#00B900"
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "Read" if _is_English else "既読",
                            "data": f"action=read%{msg_id}",
                            "displayText": "既読にします"
                        },
                        "color": "#00B900"
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "GLinK",
                            "data": f"action=Glink%{msg_id}"
                        },
                        "color": "#00B900"
                    },
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": f"{_importance}",
                                "data": f"label=importance&msg_id={msg_id}",
                                "displayText": f"Importanceを変更します"
                            },
                            "color": "#AAAAAA"
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "postback",
                                "label": f"{_category}",
                                "data": f"label=category&msg_id={msg_id}",
                                "displayText": f"Categoryを変更します"
                            },
                            "color": "#AAAAAA"
                        }
                    ]
                },
            ],
            "flex": 0
        }
    }

    messages = [
        {
            "type": "flex",
            "altText": "メール詳細",
            "contents": bubble
        }
    ]

    return messages