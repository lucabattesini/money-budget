import { toaster, Toaster } from "../components/ui/toaster";

export default function customToaster(title, type, description) {
    toaster.create({
        title: title,
        type: type,
        description: description,
        status: type,
        duration: 5000,
        isClosable: true,
        position: "top",
    });
}