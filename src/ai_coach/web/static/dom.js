// Пульт: узлы DOM — одна копия на все панели (зовётся в браузере).

const SVG = "http://www.w3.org/2000/svg";

export function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

export function svgNode(tag, attrs, text) {
	const node = document.createElementNS(SVG, tag);
	for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
	if (text !== undefined) node.textContent = text;
	return node;
}
